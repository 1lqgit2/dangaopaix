using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
#if UNITY_WEBGL && !UNITY_EDITOR
using TTSDK;
#endif

// 广告平台枚举（本项目只接入抖音小游戏）
public enum AdPlatformType
{
    [InspectorName("抖音小游戏")]
    TickTok,
}


/// <summary>
/// 广告管理
/// </summary>
public class AdManager : MonoBehaviour
{
    private static AdManager instance;

    /// <summary>
    /// 全局唯一实例。
    /// 这里用属性而不是裸静态字段：初始场景 Loadscreen 是「additive 加载 Master → 再卸载自己」的流程，
    /// 一旦静态字段指向的物体被场景卸载销毁，属性会自动重新找一个，避免 Instance 悄悄变成 null。
    /// </summary>
    public static AdManager Instance
    {
        get
        {
            if (instance == null)
            {
                instance = FindObjectOfType<AdManager>();
            }

            return instance;
        }
    }

    [Header("平台")]
    public AdPlatformType adPlatformType = AdPlatformType.TickTok;
    [Header("小游戏ID")]
    public string AppId;
    [Header("激励视频广告位")]
    public List<string> videoAdIdList = new();
    [Header("插屏广告位")]
    public List<string> interAdIdList = new();

    private IAdPlatform platFormIns = null;
    private float lastAdClickTime;

    // 抖音 TT.InitSDK 是异步的，初始化没结束就创建广告实例会拉不到素材（真机上表现为「广告不播/不回调」）。
    // 所以平台实例统一放到初始化回调里创建，初始化期间用户点的广告先排队，初始化完成后自动补播。
    private bool sdkInitDone;
    private Action pendingRewardSuccess;
    private Action<string> pendingRewardFail;
    private Coroutine pendingRewardTimeout;

    private bool warnedEmptyVideoList;
    private bool warnedEmptyInterList;

#if !UNITY_WEBGL || UNITY_EDITOR
    [Header("编辑器调试")]
    [Tooltip("编辑器/PC 里点击设置时，用全屏遮罩模拟插屏广告，方便确认流程；真机 WebGL 不受影响")]
    public bool showMockAdInEditor = true;

    private GameObject mockInterstitialRoot;
    private Font mockAdFont;
#endif

    void Awake()
    {
        if (instance != null && instance != this)
        {
            // 已经有一个实例了（通常是初始场景里的那个），本场景内的重复实例直接销毁，
            // 避免广告平台被初始化两次。
            // 先 enabled=false：Destroy 是延迟到帧末执行的，不禁用的话本帧 Start() 仍会跑，
            // 会把 TT.InitSDK 和广告平台再初始化一遍。
            enabled = false;
            Destroy(gameObject);
            return;
        }

        instance = this;

        // 关键：LoadscreenScene 用 LoadSceneAsync(1, Additive) 加载 Master，随后 UnloadSceneAsync(0)
        // 卸载初始场景。AdManager 如果留在初始场景里，会跟着一起被销毁，静态 Instance 变成
        // 「已销毁对象」（Unity 里 == null 为 true），点广告时就报「场景里没有 AdManager」。
        // 所以这里把它移到根节点并设为跨场景常驻。
        if (transform.parent != null)
        {
            transform.SetParent(null, true);
        }

        if (transform.root == transform)
        {
            DontDestroyOnLoad(gameObject);
            Debug.Log("[广告] AdManager 已设为跨场景常驻");
        }
        else
        {
            Debug.LogWarning("[广告] AdManager 不在根节点，无法跨场景常驻，切换场景后广告可能失效");
        }
    }

    private void Start()
    {
        this.lastAdClickTime = -1f;

        if (string.IsNullOrEmpty(this.AppId))
        {
            // AppID 只影响埋点回传，不影响广告播放
            Debug.Log("[广告] 未填写小游戏 AppID，广告可正常播放，仅埋点上报不可用");
        }

        if (this.videoAdIdList == null || this.videoAdIdList.Count == 0)
        {
            Debug.LogWarning("[广告] 激励视频广告位为空，激励视频将无法播放");
        }

        if (this.interAdIdList == null || this.interAdIdList.Count == 0)
        {
            Debug.LogWarning("[广告] 插屏广告位为空，将使用内置默认广告位");
        }

        // 初始化抖音 SDK，成功后再创建广告平台
        this.InitTTSdk(this.OnSdkInitDone);
        this.StartCoroutine(this.SdkInitFallbackRoutine(8f));
    }

    /// <summary>
    /// 兜底：万一 TT.InitSDK 的回调没有回来（老版本容器 / 初始化异常），
    /// 8 秒后照样把广告平台建起来，避免整局游戏都点不出广告。
    /// </summary>
    private IEnumerator SdkInitFallbackRoutine(float seconds)
    {
        yield return new WaitForSecondsRealtime(seconds);

        if (this.sdkInitDone) yield break;

        Debug.LogWarning("[广告] 抖音 SDK 初始化回调超时，尝试直接创建广告平台");
        this.OnSdkInitDone();
    }

    private void OnSdkInitDone()
    {
        this.sdkInitDone = true;
        this.CreateAdPlatform();

        // 初始化期间排队的激励视频请求，现在补播
        this.FlushPendingReward();
    }

    private void InitTTSdk(Action onDone)
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        try
        {
            // OnTTContainerInitCallback 的签名是 void Invoke(int code, ContainerEnv env)
            TT.InitSDK((code, env) =>
            {
                if (code == 0)
                {
                    Debug.Log("[抖音SDK] 初始化完成");
                }
                else
                {
                    // 1 = SDK 版本不支持，2 = 引擎版本不支持
                    Debug.LogWarning($"[抖音SDK] 初始化失败，错误码 {code}");
                }

                onDone?.Invoke();
            });
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[抖音SDK] 初始化异常（不影响广告接口调用）：{e.Message}");
            onDone?.Invoke();
        }
#else
        Debug.Log("[广告] 当前不是抖音小游戏 WebGL 真机环境，广告平台不初始化");
        onDone?.Invoke();
#endif
    }

    private void CreateAdPlatform()
    {
        if (this.platFormIns != null) return;

        switch (this.adPlatformType)
        {
            case AdPlatformType.TickTok:
#if UNITY_WEBGL && !UNITY_EDITOR
                try
                {
                    // 抖音激励视频只支持单个实例，所以激励视频固定用第一个广告位，
                    // 否则每次随机换 ID 都会触发「销毁旧实例 + 重建」，容易丢回调、丢奖励。
                    this.platFormIns = new TikTokPlatform(this.AppId, this.GetVideoAdId(), this.GetRandScreenAdId());
                    Debug.Log($"[广告] 抖音小游戏广告已就绪，AppID={this.AppId}，激励视频={this.GetVideoAdId()}，插屏={this.GetRandScreenAdId()}");
                }
                catch (Exception e)
                {
                    Debug.LogError($"[广告] 创建抖音广告平台失败：{e.Message}");
                }
#else
                Debug.Log("[广告] 抖音小游戏广告仅在 WebGL 真机启用，当前平台跳过初始化");
#endif
                break;
        }

#if UNITY_WEBGL && !UNITY_EDITOR
        if (this.platFormIns == null)
        {
            Debug.LogError($"[广告] 广告平台初始化失败：{this.adPlatformType}");
        }
#endif
    }


    /// <summary>
    /// 播放插屏广告（点击设置等界面切换时调用）
    /// </summary>
    public void ShowInterstitialAd()
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        if (this.platFormIns == null)
        {
            // 抖音 SDK 初始化还没完成时点进来会走到这里，等下一次再播即可，不必报错打断玩家
            Debug.LogWarning("[广告] 广告平台尚未就绪，跳过本次插屏广告");
            return;
        }

        try
        {
            this.platFormIns.ShowInterstitialAd(this.GetRandScreenAdId());
        }
        catch (Exception e)
        {
            Debug.LogError($"[广告] 展示插屏广告异常：{e.Message}");
        }
#else
        // 编辑器 / PC 没有抖音小游戏运行时，插屏广告无法真播。
        // 这里用一个全屏遮罩模拟一下，方便在编辑器里确认「点击设置 → 出现插屏 → 关闭后回到设置」的流程。
        Debug.Log("[广告] 当前环境没有真实插屏广告（编辑器/PC），模拟展示一次插屏");
        if (this.showMockAdInEditor)
        {
            this.StartCoroutine(this.MockInterstitialRoutine(2.5f));
        }
#endif
    }

#if !UNITY_WEBGL || UNITY_EDITOR
    /// <summary>
    /// 编辑器里的插屏模拟：全屏遮罩 + 倒计时，几秒后自动关闭。
    /// 仅用于确认调用链，真机 WebGL 不会编译这段代码。
    /// </summary>
    private IEnumerator MockInterstitialRoutine(float seconds)
    {
        if (this.mockInterstitialRoot != null)
        {
            Destroy(this.mockInterstitialRoot);
            this.mockInterstitialRoot = null;
        }

        GameObject canvasGo = new GameObject("MockInterstitialCanvas");
        canvasGo.transform.SetParent(this.transform, false);

        Canvas canvas = canvasGo.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.sortingOrder = 32760; // 盖住所有 UI，包括弹窗

        CanvasScaler scaler = canvasGo.AddComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1080f, 1920f);
        scaler.screenMatchMode = CanvasScaler.ScreenMatchMode.MatchWidthOrHeight;
        scaler.matchWidthOrHeight = 1f;

        canvasGo.AddComponent<GraphicRaycaster>();

        GameObject bg = new GameObject("Bg", typeof(RectTransform));
        bg.transform.SetParent(canvasGo.transform, false);
        Image bgImage = bg.AddComponent<Image>();
        bgImage.color = new Color(0.09f, 0.07f, 0.05f, 0.86f);
        RectTransform bgRect = bgImage.rectTransform;
        bgRect.anchorMin = Vector2.zero;
        bgRect.anchorMax = Vector2.one;
        bgRect.offsetMin = Vector2.zero;
        bgRect.offsetMax = Vector2.zero;

        Font font = this.GetMockAdFont();

        GameObject titleGo = new GameObject("Title", typeof(RectTransform));
        titleGo.transform.SetParent(bg.transform, false);
        Text title = titleGo.AddComponent<Text>();
        title.font = font;
        title.fontSize = 92;
        title.fontStyle = FontStyle.Bold;
        title.alignment = TextAnchor.MiddleCenter;
        title.color = new Color(1f, 0.87f, 0.6f, 1f);
        title.raycastTarget = false; // 让点击穿透到遮罩上的关闭按钮
        title.text = "AD";
        RectTransform titleRect = title.rectTransform;
        titleRect.anchorMin = new Vector2(0f, 0.5f);
        titleRect.anchorMax = new Vector2(1f, 0.5f);
        titleRect.sizeDelta = new Vector2(0f, 200f);
        titleRect.anchoredPosition = new Vector2(0f, 80f);

        GameObject tipGo = new GameObject("Tip", typeof(RectTransform));
        tipGo.transform.SetParent(bg.transform, false);
        Text tip = tipGo.AddComponent<Text>();
        tip.font = font;
        tip.fontSize = 40;
        tip.alignment = TextAnchor.MiddleCenter;
        tip.color = new Color(1f, 1f, 1f, 0.75f);
        tip.raycastTarget = false;
        tip.text = "点击任意处关闭（编辑器模拟插屏）";
        RectTransform tipRect = tip.rectTransform;
        tipRect.anchorMin = new Vector2(0f, 0.5f);
        tipRect.anchorMax = new Vector2(1f, 0.5f);
        tipRect.sizeDelta = new Vector2(0f, 80f);
        tipRect.anchoredPosition = new Vector2(0f, -60f);

        this.mockInterstitialRoot = canvasGo;

        // 点击遮罩即可关闭，交互和真机插屏（点关闭 / 空白处）保持一致
        Button closeBtn = bg.AddComponent<Button>();
        closeBtn.targetGraphic = bgImage;
        closeBtn.transition = Selectable.Transition.None;
        closeBtn.onClick.AddListener(() =>
        {
            if (this.mockInterstitialRoot != null)
            {
                Destroy(this.mockInterstitialRoot);
                this.mockInterstitialRoot = null;
            }
            Debug.Log("[广告] 模拟插屏已关闭，回到设置面板");
        });

        yield return new WaitForSecondsRealtime(seconds);

        if (this.mockInterstitialRoot != null)
        {
            Destroy(this.mockInterstitialRoot);
            this.mockInterstitialRoot = null;
            Debug.Log("[广告] 模拟插屏自动关闭，回到设置面板");
        }
    }

    /// <summary>编辑器模拟遮罩用字体：优先系统雅黑（能显示中文），拿不到就退回内置字体</summary>
    private Font GetMockAdFont()
    {
        if (this.mockAdFont != null)
        {
            return this.mockAdFont;
        }

        try
        {
            this.mockAdFont = Font.CreateDynamicFontFromOSFont(
                new string[] { "Microsoft YaHei", "PingFang SC", "SimHei" }, 40);
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[广告] 创建模拟广告字体失败：{e.Message}");
        }

        if (this.mockAdFont == null)
        {
            try
            {
                // Unity 2021 起内置字体资源名为 LegacyRuntime.ttf（旧版是 Arial.ttf）
                this.mockAdFont = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[广告] 加载内置字体失败：{e.Message}");
            }
        }

        if (this.mockAdFont == null)
        {
            Debug.LogWarning("[广告] 模拟插屏没有可用字体，遮罩上的文字不会显示（不影响链路验证）");
        }

        return this.mockAdFont;
    }
#endif

    /// <summary>
    /// 跳转场景
    /// </summary>
    /// <param name="onSuccess">成功回调</param>
    /// <param name="onFail">失败回调</param>
    public void NavigateToScene(Action onSuccess = null, Action<string> onFail = null)
    {
        if (this.platFormIns == null)
        {
            Debug.LogError("广告平台实例未初始化，无法跳转场景");
            onFail?.Invoke("广告平台实例未初始化");
            return;
        }

        try
        {
            this.platFormIns.NavigateToScene(onSuccess, onFail);
        }
        catch (Exception e)
        {
            Debug.LogError($"跳转场景时发生异常：{e.Message}");
            onFail?.Invoke($"跳转场景时发生异常：{e.Message}");
        }
    }

    public void ShareGame(Action<bool> callBack = null)
    {
        this.platFormIns?.ShareGame(callBack);
    }

    /// <summary>
    /// 播放激励视频广告
    /// </summary>
    /// <param name="onSuccess">看完广告后的发奖回调，只有播放完成才会触发</param>
    /// <param name="onFail">失败回调（未看完 / 加载失败 / 未初始化）</param>
    public void ShowRewardedVideoAd(Action onSuccess, Action<string> onFail)
    {
#if !UNITY_WEBGL || UNITY_EDITOR
        // 编辑器 / PC 等没有抖音小游戏运行时的环境：
        // 上面的 InitTTSdk / CreateAdPlatform 在非 WebGL 真机下会跳过初始化，
        // 如果这里再走 platFormIns，就必然失败，所有「看广告领奖励」的入口都会卡住。
        // 所以编辑器里统一模拟「广告播放完成」，直接回调发奖，方便调试；
        // 真机 WebGL 包不会进入这个分支，不影响线上逻辑。
        Debug.Log("[广告] 当前环境没有真实广告（编辑器/PC），模拟广告播放完成 → 直接发放奖励");
        onSuccess?.Invoke();
        return;
#else
        if (!this.CheckTimeLimit())
        {
            onFail?.Invoke("点击过于频繁，请稍后再试");
            return;
        }

        // 初始化还在进行中：排队等初始化完成，避免这一下点击白白丢掉
        if (this.platFormIns == null && !this.sdkInitDone)
        {
            this.QueuePendingReward(onSuccess, onFail);
            return;
        }

        if (this.platFormIns == null)
        {
            Debug.LogError("[广告] 广告平台实例未初始化，无法显示广告");
            onFail?.Invoke("广告平台实例未初始化");
            return;
        }

        this.ShowRewardedVideoAdInternal(onSuccess, onFail);
#endif
    }

    private void ShowRewardedVideoAdInternal(Action onSuccess, Action<string> onFail)
    {
        string adId = this.GetVideoAdId();
        if (string.IsNullOrEmpty(adId))
        {
            onFail?.Invoke("未配置激励视频广告位");
            return;
        }

        try
        {
            this.platFormIns.ShowRewardedVideoAd(adId, onSuccess, onFail);
        }
        catch (Exception e)
        {
            Debug.LogError($"显示广告时发生异常：{e.Message}");
            onFail?.Invoke($"显示广告时发生异常：{e.Message}");
        }
    }

    /// <summary>
    /// 初始化未完成时的排队逻辑：只保留最后一次点击，10 秒内初始化还没完成就失败返回。
    /// </summary>
    private void QueuePendingReward(Action onSuccess, Action<string> onFail)
    {
        Debug.Log("[广告] 广告 SDK 正在初始化，本次观看请求已排队，初始化完成后自动播放");

        this.pendingRewardSuccess = onSuccess;
        this.pendingRewardFail = onFail;

        if (this.pendingRewardTimeout != null)
        {
            StopCoroutine(this.pendingRewardTimeout);
        }
        this.pendingRewardTimeout = StartCoroutine(this.PendingRewardTimeoutRoutine(10f));
    }

    private IEnumerator PendingRewardTimeoutRoutine(float seconds)
    {
        yield return new WaitForSecondsRealtime(seconds);

        this.pendingRewardTimeout = null;

        if (this.pendingRewardSuccess == null && this.pendingRewardFail == null)
        {
            yield break;
        }

        var fail = this.pendingRewardFail;
        this.pendingRewardSuccess = null;
        this.pendingRewardFail = null;

        Debug.LogError("[广告] 广告初始化超时，本次观看请求作废");
        fail?.Invoke("广告初始化超时，请稍后再试");
    }

    private void FlushPendingReward()
    {
        if (this.pendingRewardSuccess == null && this.pendingRewardFail == null) return;

        var onSuccess = this.pendingRewardSuccess;
        var onFail = this.pendingRewardFail;
        this.pendingRewardSuccess = null;
        this.pendingRewardFail = null;

        if (this.pendingRewardTimeout != null)
        {
            StopCoroutine(this.pendingRewardTimeout);
            this.pendingRewardTimeout = null;
        }

        if (this.platFormIns == null)
        {
            onFail?.Invoke("广告平台初始化失败");
            return;
        }

        this.ShowRewardedVideoAdInternal(onSuccess, onFail);
    }


    // 激励视频广告位：固定取第一个（抖音激励视频只支持单实例）
    private string GetVideoAdId()
    {
        if (this.videoAdIdList == null || this.videoAdIdList.Count == 0)
        {
            if (!this.warnedEmptyVideoList)
            {
                this.warnedEmptyVideoList = true;
                Debug.LogError("[广告] 激励视频广告位列表为空：请把「激励视频」广告位 ID 填到 AdManager 的 videoAdIdList（不要填插屏 / Banner 的 ID）");
            }
            // 以前这里兜底一个写死的广告位，一旦它不属于当前小游戏，
            // 真机就会刷 createVideoAd:fail / code=1002，玩家领不到奖励还看不出原因。
            // 现在返回空串，由调用方直接失败，问题一眼可见。
            return string.Empty;
        }

        return this.videoAdIdList[0];
    }

    // 随机取一个激励视频广告位ID（保留给多广告位场景使用）
    private string GetRandVideoAdId()
    {
        if (this.videoAdIdList == null || this.videoAdIdList.Count == 0)
        {
            return this.GetVideoAdId();
        }
        int index = UnityEngine.Random.Range(0, this.videoAdIdList.Count);
        return this.videoAdIdList[index];
    }

    // 插屏广告位：固定取第一个。
    // 注意不能随机取：TikTokPlatform 里广告位一变就会销毁重建实例，
    // 而新建的实例还没 Load 完，会直接「本次跳过」，配置多个广告位时反而一次都播不出来。
    private string GetRandScreenAdId()
    {
        if (this.interAdIdList == null || this.interAdIdList.Count == 0)
        {
            if (!this.warnedEmptyInterList)
            {
                this.warnedEmptyInterList = true;
                Debug.LogWarning("[广告] 未配置插屏广告位，本次不展示插屏。请在 AdManager 的 interAdIdList 里填写插屏广告位 ID。");
            }
            // 返回空串而不是硬编码一个广告位：拿错误的广告位去创建只会得到
            // createInterstitialAd:fail（例如填成了 Banner 类型的代码位），
            // 既播不出来还刷一屏报错，不如直接跳过。
            return string.Empty;
        }

        return this.interAdIdList[0];
    }

    // 限制 0.5 秒内广告只能触发一次
    // 用 unscaledTime：广告播放时 Time.timeScale 被置 0，Time.time 会停住，
    // 用 Time.time 会导致「看完广告马上点下一个奖励」被误判成连点而拿不到奖励。
    private bool CheckTimeLimit()
    {
        if (this.lastAdClickTime > 0f && Time.unscaledTime - this.lastAdClickTime < 0.5f)
        {
            Debug.LogWarning("广告点击过于频繁，请稍后再试。");
            return false;
        }

        this.lastAdClickTime = Time.unscaledTime;
        return true;
    }
}
