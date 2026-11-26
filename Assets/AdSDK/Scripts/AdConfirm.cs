using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// 激励广告弹窗
/// </summary>
public class AdConfirm : MonoBehaviour
{
    private static AdConfirm instance;

    /// <summary>
    /// 是否正在由 Show() 动态创建实例。
    /// Awake 里要靠它区分「Show 创建的新实例」和「场景里预先摆好的那个」。
    /// </summary>
    private static bool creatingFromShow;

    [SerializeField] private Button btnClose;
    [SerializeField] private Button btnConfirm;
    private Action onCompleted;

    /// <summary>场景里直接打开弹窗（jiliBtn）时使用的默认奖励金币数，和预制体上显示的数字保持一致</summary>
    [SerializeField] private int defaultRewardCoin = 100;

    /// <summary>面板中间显示的金币数量（留空时自动按 panel/award/value 查找）</summary>
    [SerializeField] private Text valueText;

    public static void Show(Action callBack)
    {
        if (instance == null)
        {
            // 加载 AdConfirm 预制体
            GameObject prefab = Resources.Load<GameObject>("AdConfirm");
            if (prefab == null)
            {
                Debug.LogError("AdConfirm 预制体未找到，请确保其位于 Resources 文件夹中。");
                return;
            }

            // 实例化 AdConfirm
            creatingFromShow = true;
            GameObject adConfirmInstance = Instantiate(prefab);
            creatingFromShow = false;
            instance = adConfirmInstance.GetComponent<AdConfirm>();

            if (instance == null)
            {
                Debug.LogError("AdConfirm 脚本未附加到预制体上，请检查预制体设置。");
                Destroy(adConfirmInstance);
                return;
            }
        }

        // 设置回调并显示弹窗
        instance.onCompleted = callBack;
        instance.gameObject.SetActive(true);
    }

    private void Awake()
    {
        if (instance != null && instance != this)
        {
            Destroy(gameObject);
            return;
        }

        instance = this;

        // 只有 Show() 动态创建出来的实例才需要在实例化瞬间隐藏（避免闪一帧）。
        // 场景里预摆的那个（jiliBtn 用 SetActive(true) 打开）不能在这里关掉自己，
        // 否则就是「点一下闪一下、什么都没发生」。
        if (creatingFromShow)
        {
            gameObject.SetActive(false);
        }

        // 没人给回调（直接在场景里打开）时，按默认「看广告领金币」处理
        if (onCompleted == null)
        {
            onCompleted = this.GrantDefaultReward;
        }

        // 弹窗永远显示在最上层：浮在侧边栏/激励按钮和其它弹窗之上
        transform.SetAsLastSibling();

        this.SyncRewardText();

        btnClose?.onClick.AddListener(this.OnClose);
        btnConfirm?.onClick.AddListener(this.OnConfirm);
    }

    /// <summary>让面板上显示的金币数跟 defaultRewardCoin 一致，改数值时不用再手动改文字</summary>
    private void SyncRewardText()
    {
        if (valueText == null)
        {
            Transform t = transform.Find("panel/award/value");
            if (t != null)
            {
                valueText = t.GetComponent<Text>();
            }
        }

        if (valueText != null)
        {
            valueText.text = this.defaultRewardCoin.ToString();
        }
    }


    private void OnClose()
    {
        this.gameObject.SetActive(false);
    }

    void OnConfirm()
    {
        Debug.Log("[广告] 点击「确认看广告」，开始播放激励视频");
#if UNITY_EDITOR
        onCompleted?.Invoke();
        this.OnClose();
#else
        if (AdManager.Instance == null)
        {
            Debug.LogError("[广告] 场景里没有 AdManager，无法播放广告");
            OnAdError("广告服务未初始化");
            return;
        }
        AdManager.Instance.ShowRewardedVideoAd(OnAdWatched, OnAdError);
#endif
    }

    private void OnAdWatched()
    {
        Debug.Log("[广告] 广告观看完成，发放奖励");
        onCompleted?.Invoke();
        OnClose();
    }

    private void OnAdError(string errorMessage)
    {
        Debug.LogError($"广告播放失败: {errorMessage}");
        ShowAdError();
    }

    /// <summary>
    /// 场景里直接打开弹窗（例如主界面左上角的 jiliBtn）时使用：看完广告发金币并弹出奖励面板。
    /// </summary>
    private void GrantDefaultReward()
    {
        int coin = this.defaultRewardCoin;

        if (GameManager.Instance == null)
        {
            Debug.LogError("[广告] GameManager 未就绪，无法发放默认奖励");
            return;
        }

        var rewards = new List<ItemData>
        {
            new ItemData { ItemType = ItemType.Coin, amount = coin }
        };

        GameManager.Instance.GetItemRewards(rewards);

        if (UIManager.instance != null)
        {
            UIManager.instance.ShowPanelItemsReward();
        }

        Debug.Log($"[广告] 激励奖励已发放：{coin} 金币");
    }

    /// <summary>
    /// 广告不可用（加载失败 / 未看完 / 平台未初始化）时给玩家一个短暂提示，
    /// 避免「点了没反应」被误认为奖励没发。
    /// </summary>
    public static void ShowAdError()
    {
        GameObject adErrorPrefab = Resources.Load<GameObject>("AdError");
        if (adErrorPrefab == null)
        {
            Debug.LogWarning("[广告] AdError 预制体未找到，跳过提示");
            return;
        }

        GameObject adErrorInstance = Instantiate(adErrorPrefab);

        // 预制体自带的 Canvas 如果是相机模式，可能在当前场景不可见，统一改成最顶层 Overlay
        Canvas canvas = adErrorInstance.GetComponent<Canvas>();
        if (canvas == null)
        {
            canvas = adErrorInstance.GetComponentInChildren<Canvas>();
        }
        if (canvas != null)
        {
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 30000;
        }

        // 1.5 秒后销毁实例
        Destroy(adErrorInstance, 1.5f);
    }
}
