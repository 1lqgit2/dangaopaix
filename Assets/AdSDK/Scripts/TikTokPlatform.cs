using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;

// TTSDK 仅在抖音小游戏（WebGL 真机）环境可用，编辑器/其他平台下排除，避免找不到 TTSDK 命名空间
#if UNITY_WEBGL && !UNITY_EDITOR
using TTSDK;
using TTSDK.UNBridgeLib.LitJson;

/*
 * 抖音平台广告
 */
public class TikTokPlatform : IAdPlatform
{
    /// <summary>
    /// 是否向第三方（ecpm.xxhygames.com）上报 openid/机型等数据做 ECPM 与转化回传。
    /// 默认关闭：上面报会把用户信息发到外部服务器，抖音审核和隐私政策里必须申报，
    /// 确认是自己的后台、且已在上架材料里写明后再改成 true。
    /// </summary>
    public static bool EnableRemoteTracking = false;

    // 小游戏ID
    private readonly string miniAppid;

    // 激励视频
    private TTRewardedVideoAd rewardedVideoAd = null;
    private string videoAdId = "";
    private Action onRewardSuccess;
    private Action<string> onRewardFail;
    private float prevTimeScale = 1f;
    private bool isRewardedShowing;   // 是否正在播放（防止重复 Show 导致回调错乱）
    private bool rewardGranted;       // 本次广告是否已发奖（防止重复发奖/漏发）
    private int rewardSessionId;      // 播放场次，用于让超时兜底只作用于当前这一场

    // 激励视频失败的冷却 / 防刷屏：
    // 原来是 OnError → FailRewardedAd → PreloadRewardedAd → Load → OnError 无限循环，
    // 广告位配错时真机几秒钟就能刷出几十条 createVideoAd:fail，日志和控制台全被刷爆，
    // 而且玩家点「看广告」也只会拿到一串报错。现在按错误类型进入冷却，冷却期内不再自动重试。
    private const float RewardRetryBackoffSeconds = 30f;
    private const float RewardConfigErrorBlockSeconds = 300f;
    private float rewardLoadBlockedUntil;
    private bool loggedRewardConfigError;

    // 插屏广告
    private TTInterstitialAd interAdIns;
    private string interAdId = "";
    private float moduleStartTime;
    private float lastShowTime;
    // 点了「看插屏」但素材还没 Load 完时，先记下来，等 OnLoad 回调到了自动补展示一次，
    // 否则第一次点设置会因为「尚未加载完成」被直接跳过，玩家看起来就是没广告。
    private bool pendingInterShow;

    // 埋点
    private readonly string ecpmURL = "https://ecpm.xxhygames.com/openid/openlog/insertlog";  // ECPM后台地址
    private readonly string conversionURL = "https://analytics.oceanengine.com/api/v2/conversion";   // 巨量引擎API接口

    private TTSystemInfo systemInfo;

    public TikTokPlatform(string appId, string videoAdId, string interAdId)
    {
        this.miniAppid = appId ?? "";
        this.videoAdId = videoAdId;
        this.interAdId = interAdId;
        if (string.IsNullOrEmpty(this.miniAppid))
        {
            // AppID 只用于 ECPM/转化回传，广告本身按广告位 ID 播放，不影响收益流程。
            Debug.Log("[抖音广告] 未填写小游戏 AppID，广告可正常播放，仅埋点上报不可用");
        }
        else if (EnableRemoteTracking && !this.miniAppid.EndsWith("07"))
        {
            // 只有开启回传时才需要 AppID 格式校验，否则这条警告纯属噪音
            Debug.LogWarning($"[抖音广告] AppID「{this.miniAppid}」格式可能不匹配回传接口，广告播放不受影响");
        }

        if (EnableRemoteTracking)
        {
            try
            {
                this.Login();
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[抖音广告] 埋点初始化失败（不影响广告）：{e.Message}");
            }
        }

        // 编辑器里 TT 接口是 mock，可能直接抛异常；真机上按正常流程创建。
        // 注意：这里只在 TT.InitSDK 回调之后才会被调用（见 AdManager），否则广告实例拉不到素材。
        // 插屏不在这里预创建：改为点亮设置时按需创建，避免失败场景在启动阶段反复报错。
        try
        {
            this.EnsureRewardedAd(this.videoAdId);
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[抖音广告] 初始化广告实例失败（真机上会自动重试）：{e.Message}");
        }

        moduleStartTime = Time.realtimeSinceStartup;
        lastShowTime = -InterShowIntervalSeconds;
    }


    #region 插屏广告

    // 平台频率限制（官方文档 tt.createInterstitialAd）：
    // 1. 小游戏启动后前 30 秒不能展示插屏
    // 2. 两次插屏展示间隔 >= 60 秒
    // 3. 展示过激励视频后，再展示插屏需间隔 >= 60 秒
    private const float InterStartupGuardSeconds = 30f;
    private const float InterShowIntervalSeconds = 60f;
    private const float InterAfterRewardSeconds = 60f;

    // 创建失败后的冷却：避免玩家每点一次设置就撞一次必然失败的创建
    // （开发者工具沙盒不支持插屏，tt.createInterstitialAd 会直接 fail）
    private const float InterCreateBackoffSeconds = 30f;
    // 创建后等回调的兜底：OnLoad/OnError 都没来时不至于永久卡住
    private const float InterCreateTimeoutSeconds = 10f;

    private float lastVideoShowTime = -999f;
    private float interCreateBlockedUntil;
    private bool interCreating;
    private float interCreatingSince;

    /// <summary>
    /// 展示插屏。平台限制：启动 30s 内、两次插屏间隔 60s 内、激励视频后 60s 内都不允许展示。
    /// 实例按需创建；没加载完时先记 pending，OnLoad 到了补展示一次。
    /// </summary>
    public override void ShowInterstitialAd(string AdId)
    {
        // 广告位变化时清掉旧实例，避免继续拿旧广告位创建
        if (!string.IsNullOrEmpty(AdId) && this.interAdId != AdId)
        {
            this.interAdId = AdId;
            this.RemoveInterstitialAd();
        }

        // 没配广告位就不要去创建：创建必然失败，还会刷一屏错误
        if (string.IsNullOrEmpty(this.interAdId))
        {
            this.pendingInterShow = false;
            Debug.LogWarning("[抖音广告] 未配置插屏广告位，跳过插屏展示");
            return;
        }

        // 回调没来时的兜底，避免 interCreating 永久为 true 导致之后都创建不了
        if (this.interCreating && Time.realtimeSinceStartup - this.interCreatingSince > InterCreateTimeoutSeconds)
        {
            this.interCreating = false;
            Debug.LogWarning("[抖音广告] 插屏创建超时（没收到 OnLoad/OnError），丢弃引用后下次重试");
            // 只清引用不 Destroy：此时 load 的 Promise 可能还没结束，主动销毁会多出一条 Uncaught (in promise)
            this.ClearInterstitialRef();
        }

        float now = Time.realtimeSinceStartup;

        if (now - this.moduleStartTime < InterStartupGuardSeconds)
        {
            this.pendingInterShow = false;
            Debug.Log($"[抖音广告] 启动 {InterStartupGuardSeconds:0} 秒内不能展示插屏，剩余 {InterStartupGuardSeconds - (now - this.moduleStartTime):F1} 秒");
            return;
        }

        if (now - this.lastShowTime < InterShowIntervalSeconds)
        {
            this.pendingInterShow = false;
            Debug.Log($"[抖音广告] 两次插屏间隔需 >= {InterShowIntervalSeconds:0} 秒，剩余 {InterShowIntervalSeconds - (now - this.lastShowTime):F1} 秒");
            return;
        }

        if (now - this.lastVideoShowTime < InterAfterRewardSeconds)
        {
            this.pendingInterShow = false;
            Debug.Log($"[抖音广告] 激励视频后需间隔 {InterAfterRewardSeconds:0} 秒才能展示插屏，剩余 {InterAfterRewardSeconds - (now - this.lastVideoShowTime):F1} 秒");
            return;
        }

        if (now < this.interCreateBlockedUntil)
        {
            this.pendingInterShow = false;
            Debug.Log($"[抖音广告] 插屏创建冷却中，{this.interCreateBlockedUntil - now:F0} 秒后再试");
            return;
        }

        if (this.interAdIns == null)
        {
            this.pendingInterShow = true;
            this.CreateInterstitialAd();
            return;
        }

        bool loaded = false;
        try
        {
            loaded = interAdIns.IsLoaded();
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[抖音广告] 查询插屏状态异常：{e.Message}");
        }

        if (!loaded)
        {
            this.pendingInterShow = true;
            Debug.Log("[抖音广告] 插屏尚未加载完成，加载完成后自动展示");
            return;
        }

        try
        {
            interAdIns.Show();
            this.lastShowTime = now;
            this.pendingInterShow = false;
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[抖音广告] 展示插屏异常：{e.Message}");
        }
    }

    /// <summary>
    /// 按需创建插屏实例并 Load。失败进入冷却，避免每次点击都刷一屏同样的错误。
    /// </summary>
    private void CreateInterstitialAd()
    {
        if (string.IsNullOrEmpty(this.interAdId)) return;
        if (this.interCreating) return;

        this.interCreating = true;
        this.interCreatingSince = Time.realtimeSinceStartup;
        Debug.Log($"[抖音广告] 创建插屏实例，广告位：{this.interAdId}");

        try
        {
            this.interAdIns = TT.CreateInterstitialAd(new CreateInterstitialAdParam { InterstitialAdId = this.interAdId });
        }
        catch (Exception e)
        {
            this.OnInterstitialCreateFailed($"创建插屏异常：{e.Message}");
            return;
        }

        if (this.interAdIns == null)
        {
            this.OnInterstitialCreateFailed("创建插屏返回空实例");
            return;
        }

        this.interAdIns.OnClose += () =>
        {
            Debug.Log("[抖音广告] 插屏关闭");
            this.pendingInterShow = false;
            // 插屏实例只能展示一次，关闭后平台已自动销毁，这里只清引用，下次需要时再创建
            this.ClearInterstitialRef();
        };

        this.interAdIns.OnLoad += () =>
        {
            this.interCreating = false;
            Debug.Log("[抖音广告] 插屏加载完成");
            this.TryShowPendingInterstitial();
        };

        this.interAdIns.OnError += (code, message) =>
        {
            this.OnInterstitialCreateFailed($"插屏异常 code={code} msg={message}");
        };

        try
        {
            this.interAdIns.Load();
        }
        catch (Exception e)
        {
            this.OnInterstitialCreateFailed($"加载插屏异常：{e.Message}");
        }
    }

    private void OnInterstitialCreateFailed(string reason)
    {
        this.interCreating = false;
        this.pendingInterShow = false;
        this.interCreateBlockedUntil = Time.realtimeSinceStartup + InterCreateBackoffSeconds;
        // 只清引用：OnError 往往伴随还没结束的 load Promise，此时 Destroy 会多报一条 Uncaught (in promise)
        this.ClearInterstitialRef();

        Debug.LogWarning($"[抖音广告] {reason}（广告位 {this.interAdId}；{InterCreateBackoffSeconds:0} 秒内不再重试。开发者工具沙盒不支持插屏，请用真机验证）");
    }

    /// <summary>
    /// 点了插屏但素材还没加载完：等 OnLoad 到了补展示一次。
    /// 平台限制（启动 30 秒 / 插屏间隔 60 秒 / 激励视频后 60 秒）仍然优先，超限就放弃这次。
    /// </summary>
    private void TryShowPendingInterstitial()
    {
        if (!this.pendingInterShow) return;

        this.pendingInterShow = false;

        if (this.interAdIns == null) return;

        try
        {
            if (!this.interAdIns.IsLoaded()) return;
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[抖音广告] 查询插屏状态异常：{e.Message}");
            return;
        }

        float now = Time.realtimeSinceStartup;
        if (now - this.moduleStartTime < InterStartupGuardSeconds
            || now - this.lastShowTime < InterShowIntervalSeconds
            || now - this.lastVideoShowTime < InterAfterRewardSeconds)
        {
            Debug.Log("[抖音广告] 插屏已加载，但仍在平台限制时间内，本次放弃展示");
            return;
        }

        try
        {
            this.interAdIns.Show();
            this.lastShowTime = now;
            Debug.Log("[抖音广告] 插屏加载完成，补展示一次");
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[抖音广告] 补展示插屏异常：{e.Message}");
        }
    }

    /// <summary>只丢引用，不主动销毁（错误/关闭后实例由平台回收）。</summary>
    private void ClearInterstitialRef()
    {
        this.interAdIns = null;
    }

    /// <summary>换广告位时显式销毁旧实例。</summary>
    private void RemoveInterstitialAd()
    {
        var ins = this.interAdIns;
        this.interAdIns = null;
        if (ins == null) return;

        try { ins.Destroy(); }
        catch (Exception e) { Debug.LogWarning($"[抖音广告] 销毁插屏异常：{e.Message}"); }
    }

    #endregion


    #region 侧边栏

    public override void NavigateToScene(Action onSuccess, Action<string> onFail)
    {
        var data = new JsonData { ["scene"] = "sidebar" };
        TT.NavigateToScene(data,
            () =>
            {
                Debug.Log("侧边栏唤起成功");
                onSuccess?.Invoke();
            },
            () => { },
            (errCode, errMsg) =>
            {
                onFail?.Invoke(errMsg);
                Debug.LogError($"侧边栏显示异常:{errCode}, {errMsg}");
            });
    }

    #endregion

    #region 激励视频

    /// <summary>
    /// 播放激励视频。
    /// 抖音激励视频全局只支持一个实例（官方文档明确说明），所以这里不再「每次随机广告位 + 关闭后销毁重建」，
    /// 而是固定复用一个实例：只有广告位变化时才重建，关闭后只重新 Load，下次点击可以直接 Show。
    /// 发奖只在 onClose 的 isEnded == true 时触发一次，并且用 rewardGranted 兜底防重复/防漏发。
    /// </summary>
    public override void ShowRewardedVideoAd(string adId, Action onSuccess, Action<string> onFail)
    {
        Debug.Log("[抖音广告] 开始播放激励视频");

        if (this.isRewardedShowing)
        {
            Debug.LogWarning("[抖音广告] 激励视频正在播放中，忽略重复请求");
            onFail?.Invoke("广告正在播放中");
            return;
        }

        // 广告位配置错误（1002 等）或刚加载失败：此时 Show 必然被 TMAR 拒绝，
        // 只会再刷一条 API_ERROR，所以直接失败返回，等冷却结束再说。
        float now = Time.realtimeSinceStartup;
        if (now < this.rewardLoadBlockedUntil)
        {
            Debug.LogWarning($"[抖音广告] 激励视频暂不可用（{this.rewardLoadBlockedUntil - now:F0} 秒后才会重试），本次不播放");
            onFail?.Invoke("广告暂不可用，请稍后再试");
            return;
        }

        this.prevTimeScale = Time.timeScale > 0f ? Time.timeScale : 1f;
        Time.timeScale = 0; // 看广告需要暂停游戏

        this.onRewardSuccess = onSuccess;
        this.onRewardFail = onFail;
        this.rewardGranted = false;
        this.isRewardedShowing = true;

        this.EnsureRewardedAd(adId);

        if (this.rewardedVideoAd == null)
        {
            this.FailRewardedAd("激励视频创建失败");
            return;
        }

        try
        {
            this.rewardedVideoAd.Show();
            // 记录激励视频展示时间：插屏需要与激励视频间隔 60 秒
            this.lastVideoShowTime = Time.realtimeSinceStartup;
        }
        catch (Exception e)
        {
            Debug.LogError($"[抖音广告] 展示激励视频异常：{e.Message}");
            this.FailRewardedAd("激励视频展示失败");
            return;
        }

        // 兜底：极端情况下 SDK 既不回调 onClose 也不回调 onError，
        // 90 秒后强制解锁播放状态，避免按钮永久卡死（这种情况不会发奖）。
        int session = ++this.rewardSessionId;
        if (AdManager.Instance != null)
        {
            AdManager.Instance.StartCoroutine(this.RewardWatchdog(session));
        }
    }

    private IEnumerator RewardWatchdog(int session)
    {
        float start = Time.unscaledTime;
        while (this.isRewardedShowing && this.rewardSessionId == session && Time.unscaledTime - start < 90f)
        {
            yield return null;
        }

        if (this.isRewardedShowing && this.rewardSessionId == session)
        {
            Debug.LogWarning("[抖音广告] 激励视频 90 秒内没有任何回调，强制解锁（不发放奖励）");
            this.FailRewardedAd("广告响应超时");
        }
    }

    /// <summary>
    /// 广告失败/未看完的统一出口：恢复时间、清空回调、通知业务层，并重新预加载。
    /// </summary>
    private void FailRewardedAd(string message)
    {
        if (!this.isRewardedShowing)
        {
            // 空闲状态下的加载错误，只记录，不打断游戏
            Debug.LogWarning($"[抖音广告] 激励视频不可用：{message}");
            return;
        }

        var fail = this.onRewardFail;
        this.RestoreTimeScale();
        this.isRewardedShowing = false;

        try { fail?.Invoke(message); }
        catch (Exception e) { Debug.LogError($"[抖音广告] 激励视频失败回调异常：{e}"); }

        this.PreloadRewardedAd();
    }

    /// <summary>
    /// 看完广告的发奖出口，保证一次播放只发一次奖。
    /// </summary>
    private void GrantRewardedAdOnce()
    {
        if (this.rewardGranted) return;
        this.rewardGranted = true;

        var success = this.onRewardSuccess;
        this.RestoreTimeScale();
        this.isRewardedShowing = false;

        Debug.Log("[抖音广告] 激励视频播放完成，开始发放奖励");

        try { success?.Invoke(); }
        catch (Exception e) { Debug.LogError($"[抖音广告] 激励视频发奖回调异常：{e}"); }

        try { this.SendGameAddiction(); }
        catch (Exception e) { Debug.LogWarning($"[抖音广告] 埋点上报失败（不影响奖励）：{e.Message}"); }

        this.PreloadRewardedAd();
    }

    private void RestoreTimeScale()
    {
        this.onRewardSuccess = null;
        this.onRewardFail = null;
        Time.timeScale = this.prevTimeScale <= 0f ? 1f : this.prevTimeScale;
    }

    /// <summary>
    /// 保证有可用的激励视频实例；广告位变化或首次调用时创建。
    /// </summary>
    private void EnsureRewardedAd(string adId)
    {
        if (string.IsNullOrEmpty(adId))
        {
            adId = this.videoAdId;
        }

        if (string.IsNullOrEmpty(adId))
        {
            Debug.LogError("[抖音广告] 激励视频广告位 ID 为空，无法创建广告");
            return;
        }

        if (this.rewardedVideoAd != null && this.videoAdId == adId)
        {
            return;
        }

        this.DelRewardedVideoAd();
        this.videoAdId = adId;

        // 换了广告位，之前的失败冷却/提示记录都作废，给新广告位一次干净的机会
        this.rewardLoadBlockedUntil = 0f;
        this.loggedRewardConfigError = false;

        try
        {
            this.CreateRewardedVideoAd();
        }
        catch (Exception e)
        {
            this.rewardedVideoAd = null;
            Debug.LogError($"[抖音广告] 创建激励视频异常：{e.Message}");
        }
    }

    private void CreateRewardedVideoAd()
    {
        this.rewardedVideoAd = TT.CreateRewardedVideoAd(new CreateRewardedVideoAdParam { AdUnitId = this.videoAdId });

        this.rewardedVideoAd.OnLoad += () =>
        {
            // 加载成功说明配置/网络恢复正常，清掉冷却
            this.rewardLoadBlockedUntil = 0f;
            this.loggedRewardConfigError = false;
            Debug.Log("[抖音广告] 激励视频素材加载完成");
        };

        this.rewardedVideoAd.OnError += (errorCode, errorMessage) =>
        {
            Debug.LogError($"激励视频错误 errorCode: {errorCode}, message: {errorMessage}");
            this.OnRewardedAdError(errorCode, errorMessage);
        };

        this.rewardedVideoAd.OnClose += (ended, count) =>
        {
            Debug.Log($"[抖音广告] 激励视频关闭：是否播放完成={ended}，count={count}");

            if (ended)
            {
                // 关键：先发奖，再做其他事。之前是在发奖后又销毁重建实例，
                // 一旦销毁/重建抛异常，后面的逻辑会把这次发奖流程带崩。
                this.GrantRewardedAdOnce();
            }
            else
            {
                Debug.Log("[抖音广告] 广告未看完，不发放奖励");
                this.FailRewardedAd("广告未看完，无法领取奖励");
            }
        };

        // 创建后立刻预加载，避免首次点击 Show 时还没素材
        this.PreloadRewardedAd();
    }

    /// <summary>
    /// 激励视频加载/播放错误统一入口。
    /// 1002 = 广告位在当前小游戏里不存在，或者广告位类型不是「激励视频」；
    /// 这类配置错误重试多少次都没用，所以进入长冷却、只提示一次，避免无限重试把日志刷爆。
    /// </summary>
    private void OnRewardedAdError(int errorCode, string errorMessage)
    {
        bool configError = errorCode == 1002 || errorCode == 1001;
        float blockSeconds = configError ? RewardConfigErrorBlockSeconds : RewardRetryBackoffSeconds;
        this.rewardLoadBlockedUntil = Time.realtimeSinceStartup + blockSeconds;

        if (configError)
        {
            if (!this.loggedRewardConfigError)
            {
                this.loggedRewardConfigError = true;
                Debug.LogError(
                    $"[抖音广告] 激励视频广告位无效（code={errorCode}）：{this.videoAdId}\n" +
                    "该广告位不属于当前小游戏，或类型不是「激励视频」。请到 抖音开放平台 → 流量变现 → 广告位管理 核对：" +
                    "① 广告位属于当前小游戏 AppID；② 类型 = 激励视频；③ 状态 = 已开启。" +
                    "确认后把 ID 填进 AdManager 的 videoAdIdList，并重新打包（StarkBuilder 会用 StarkBuilderSetting 的 AppID 重写 project.config.json）。");
            }
        }
        else
        {
            Debug.LogWarning($"[抖音广告] 激励视频加载失败（code={errorCode}），{blockSeconds:0} 秒内不再自动重试：{errorMessage}");
        }

        this.FailRewardedAd(string.IsNullOrEmpty(errorMessage) ? $"广告加载失败（{errorCode}）" : errorMessage);
    }

    private void PreloadRewardedAd()
    {
        if (this.rewardedVideoAd == null) return;

        // 冷却中不要再 Load：否则 Load 失败 → OnError → 又走回来 Load，形成死循环刷屏
        if (Time.realtimeSinceStartup < this.rewardLoadBlockedUntil)
        {
            return;
        }

        try { this.rewardedVideoAd.Load(); }
        catch (Exception e) { Debug.LogWarning($"[抖音广告] 激励视频预加载失败：{e.Message}"); }
    }

    private void DelRewardedVideoAd()
    {
        if (this.rewardedVideoAd == null) return;

        var ad = this.rewardedVideoAd;
        this.rewardedVideoAd = null;

        try { ad.Destroy(); }
        catch (Exception e) { Debug.LogWarning($"[抖音广告] 销毁激励视频实例异常：{e.Message}"); }
    }

    #endregion


    #region 埋点

    private void Login()
    {
        // 1.获取系统信息
        systemInfo = TT.GetSystemInfo();
        if (systemInfo?.system == null)
            return;

        // 2.登录-获取临时登录凭证 
        TT.Login(this.onLoginSuccess, (errMsg) =>
        {
            Debug.LogError("登录失败:" + errMsg);
        }, true);
        // 3.初始化埋点
        this.InitMaidian();
    }

    private void onLoginSuccess(string code, string anonymousCode, bool isLogin)
    {
        // 2.1获取用户的基本信息
        TT.GetUserInfo((ref TTUserInfo scUserInfo) => this.onGetUserInfo(ref scUserInfo, code, anonymousCode),
            (msg) =>
            {
                Debug.LogError($"用户信息获取失败: {msg}");
            });
    }

    private void onGetUserInfo(ref TTUserInfo scUserInfo, string code, string anonymousCode)
    {
        // 2.2向ECPM后台上传设备信息
        Debug.Log(scUserInfo);
        AdManager.Instance.StartCoroutine(this.SendOpenIdLog(
            miniAppid, scUserInfo.nickName, code, anonymousCode, systemInfo, (success, res) =>
            {
                if (success && res.d != null && res.d.user != null && !string.IsNullOrEmpty(res.d.user.openid))
                {
                    string useropenid = res.d.user.openid;
                    Debug.Log("openidlog==succ== " + res);
                    string currentDate = DateTime.UtcNow.ToString("o");
                    PlayerPrefs.SetString(miniAppid + TT.GetSystemInfo().model, currentDate);
                }
                else
                {
                    Debug.Log("openidlog==fail== " + res);
                }
            }));
    }

    private IEnumerator SendOpenIdLog(string appid, string nickName, string code, string anonymousCode, TTSystemInfo sysinfores, Action<bool, OpenIdResponse> callback)
    {
        var query = $"?appid={Uri.EscapeDataString(appid)}" +
                    $"&nickName={Uri.EscapeDataString(nickName)}" +
                    $"&code={Uri.EscapeDataString(code)}" +
                    $"&anonymousCode={Uri.EscapeDataString(anonymousCode)}" +
                    $"&system={Uri.EscapeDataString(sysinfores.system)}" +
                    $"&platform={Uri.EscapeDataString(sysinfores.platform)}" +
                    $"&brand={Uri.EscapeDataString(sysinfores.brand)}" +
                    $"&modelx={Uri.EscapeDataString(sysinfores.model)}" +
                    $"&version={Uri.EscapeDataString(sysinfores.ttVersion)}" +
                    $"&SDKVersion={Uri.EscapeDataString(sysinfores.sdkVersion)}" +
                    $"&appName={Uri.EscapeDataString(sysinfores.hostName)}";

        var www = UnityWebRequest.Get(this.ecpmURL + query);
        yield return www.SendWebRequest();
        if (www.result == UnityWebRequest.Result.ConnectionError || www.result == UnityWebRequest.Result.ProtocolError)
        {
            Debug.Log("openidlog==fail== " + www.error);
            callback(false, null);
        }
        else
        {
            try
            {
                var response = JsonUtility.FromJson<OpenIdResponse>(www.downloadHandler.text);
                callback(true, response);
            }
            catch (Exception ex)
            {
                Debug.LogError("SendOpenIdLog ERROR：" + ex.Message);
                callback(false, null);
            }
        }
    }

    private void InitMaidian()
    {
        // 3.1获取小游戏启动时的参数
        var launchOptions = TT.GetLaunchOptionsSync();
        Debug.Log($"小游戏启动参数: {launchOptions}");
        if (launchOptions == null || launchOptions.Query == null || !launchOptions.Query.ContainsKey("ad_params"))
        {
            Debug.LogWarning($"小游戏:{miniAppid}没添加埋点参数");
            return;
        }

        string decodedString = Uri.UnescapeDataString(launchOptions.Query["ad_params"]);
        AdParamsData jsonval = JsonUtility.FromJson<AdParamsData>(decodedString);
        string clickid = jsonval?.log_extra?.clickid;
        if (string.IsNullOrEmpty(clickid))
        {
            Debug.LogWarning($"小游戏:{miniAppid}没点击事件埋点");
            return;
        }

        Debug.Log($"clickid: {clickid}");
        PlayerPrefs.SetString(miniAppid + "ClickId", clickid);
        if (!CanClaimReward(miniAppid + "Active"))
        {
            Debug.LogWarning($"小游戏:{miniAppid}奖励已领取，无法重复领取");
            return;
        }

        // 3.2 API上报激活数据
        long timenow = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        AdManager.Instance.StartCoroutine(SendConversionRequest(
            "active", clickid, timenow,
            (success, response) =>
            {
                Debug.Log($"激活埋点事件==={(success ? "success" : "fail")}");
                Debug.Log($"激活结果={response}");
            }
        ));
        string currentDate = DateTime.UtcNow.ToString("o");
        PlayerPrefs.SetString(miniAppid + "Active", currentDate);
    }

    /*是否允许领取奖励*/
    private bool CanClaimReward(string key)
    {
        string lastClaimDateStr = PlayerPrefs.GetString(miniAppid + key);
        if (string.IsNullOrEmpty(lastClaimDateStr))
        {
            return true;
        }

        if (!DateTime.TryParse(lastClaimDateStr, out DateTime lastClaimDate))
        {
            return true;
        }
        DateTime oneMonthAgo = DateTime.Now.AddMonths(-1);
        return lastClaimDate < oneMonthAgo;
    }

    /// <summary>
    /// API上报关键行为
    /// </summary>
    private void SendGameAddiction()
    {
        string clickid = PlayerPrefs.GetString(miniAppid + "ClickId");
        if (string.IsNullOrEmpty(clickid))
        {
            Debug.LogWarning($"小游戏:{miniAppid}没点击事件埋点");
            return;
        }

        long timenow = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        AdManager.Instance.StartCoroutine(SendConversionRequest(
                "game_addiction", clickid, timenow,
                (success, response) =>
                {
                    Debug.Log($"埋点事件===={(success ? "success" : "fail")}");
                    Debug.Log($"关键行为结果={response}");
                }
            ));
        Debug.Log("已触发激活埋点");
    }

    /// <summary>
    /// 转化回传 API
    /// </summary>
    /// <param name="eventType">回传的事件：</param>
    /// <param name="clickid">clickid 参数</param>
    /// <param name="timestamp">事件发生的毫秒级时间戳</param>
    /// <param name="callback"></param>
    /// https://event-manager.oceanengine.com/docs/8650/app_api_docs
    /// <returns></returns>
    public IEnumerator SendConversionRequest(string eventType, string clickid, long timestamp, Action<bool, string> callback)
    {
        var data = new ConversionData
        {
            event_type = eventType,
            context = new Context { ad = new Ad { callback = clickid } },
            timestamp = timestamp
        };

        string json = JsonUtility.ToJson(data);
        byte[] postData = System.Text.Encoding.UTF8.GetBytes(json);

        Dictionary<string, string> headers = new Dictionary<string, string>();
        headers.Add("Content-Type", "application/json");

        using var www = new UnityWebRequest(conversionURL, "POST");
        www.uploadHandler = new UploadHandlerRaw(postData);
        www.downloadHandler = new DownloadHandlerBuffer();
        foreach (var header in headers)
        {
            www.SetRequestHeader(header.Key, header.Value);
        }
        yield return www.SendWebRequest();
        if (www.result == UnityWebRequest.Result.ConnectionError || www.result == UnityWebRequest.Result.ProtocolError)
        {
            callback(false, www.error);
        }
        else
        {
            callback(true, www.downloadHandler.text);
        }
    }
    public override void ShareGame(Action<bool> callBack)
    {
        // 通用分享
        JsonData shareJson = new JsonData();
        shareJson["channel"] = "video";
        shareJson["title"] = "糖果乐园漫行｜一起来整理这一桌蛋糕吧";
        shareJson["extra"] = new JsonData();
        shareJson["extra"]["videoPath"] = "/xxx/xxx.mp4";//录屏分享的话，路径是 OnRecordComplete 拿到的路径
        JsonData videoTopics = new JsonData();
        videoTopics.SetJsonType(JsonType.Array);
        videoTopics.Add("Some Topic1");
        videoTopics.Add("Some Topic2");
        shareJson["extra"]["videoTopics"] = videoTopics;
        shareJson["extra"]["hashtag_list"] = videoTopics;

        Debug.Log($"ShareAppMessageBtnClicked jsonData: {videoTopics.ToJson()}");
        TT.ShareAppMessage(videoTopics, (data) =>
        {
            callBack?.Invoke(true);
            Debug.Log($"ShareAppMessage success: {videoTopics.ToJson()}");//
        },
            (errMsg) =>
            {
                callBack?.Invoke(false);
                Debug.Log($"ShareAppMessage failed: {errMsg}");
            },
            () =>
            {
                callBack?.Invoke(false);
                Debug.Log($"ShareAppMessage cancel");
            });
    }

    #endregion
}

#endif