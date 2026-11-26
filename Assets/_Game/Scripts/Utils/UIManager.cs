using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using System.Linq;
using UnityEngine.Events;
using Unity.VisualScripting;

public class UIManager : MonoBehaviour {
    public static UIManager instance;
    [SerializeField] Transform mainCanvas;
    // 弹窗层：位于悬浮按钮（侧边栏/激励）之上，避免弹窗被按钮遮挡
    [SerializeField] Transform popupLayer;
    //public GameObject backGround;
    Dictionary<UIPanelType, GameObject> listPanel = new Dictionary<UIPanelType, GameObject>();
    public bool isHasPopupOnScene = false;
    public bool isHasTutorial = false;
    public bool isHasShopPanel = false;
    public bool isHasPanelIgnoreTutorial = false;
    [SerializeField] RectTransform myRect;
    [SerializeField] GameObject ingameDebugConsole;
    [SerializeField] GameObject objBlock;
  
    public Camera mainCamera;
    public PanelTotal panelTotal;
    public PanelPlayGame panelGamePlay;
    PanelBakery panelBakery;
    PanelDecorations panelDecorations;
    PanelShop panelShop;
    PanelTopUp panelTopUp;

    [SerializeField] GameObject objSpawnPanel;
    [SerializeField] GameObject objEffect;
    [SerializeField] GameObject objCheat;
    [SerializeField] Button btnCheat;
    [SerializeField] Button btnShowUI;
    [SerializeField] Button btnTurnOffUI;

    // Start is called before the first frame update
    void Awake() {
        instance = this;
        if (ProfileManager.Instance.versionStatus == VersionStatus.Cheat)
        {
            objCheat.SetActive(true);
            btnCheat.onClick.AddListener(ShowPanelCheat);
            btnTurnOffUI.onClick.AddListener(OffUI);
            btnShowUI.onClick.AddListener(ShowUI);
        }
        else
        {
            objCheat.SetActive(false);
        }
    }

    public void TurnBlock(bool active) {
        objBlock.SetActive(active);
    }

    void OffUI() {
        objSpawnPanel.SetActive(false);
        objEffect.SetActive(false);
        objCheat.SetActive(false);
        btnShowUI.gameObject.SetActive(true);
    }

    void ShowUI() {
        objSpawnPanel.SetActive(true);
        objEffect.SetActive(true);
        objCheat.SetActive(true);
        btnShowUI.gameObject.SetActive(false);
    }

    public void ShowPanelCheat() {
        isHasPopupOnScene = true;
        objCheat.SetActive(false);
        GameObject go = GetPanel(UIPanelType.PanelCheat);
        go.transform.SetAsLastSibling();
        go.SetActive(true);
    }
    public void ClosePanelCheat() {
        isHasPopupOnScene = false;
        objCheat.SetActive(true);
        GameObject go = GetPanel(UIPanelType.PanelCheat);
        go.SetActive(false);
    }
    private void Start()
    {
        //uiPooling.FirstPooling();
        //StartCoroutine(WaitToSpawnUIPool());
        if(ingameDebugConsole != null)
        ingameDebugConsole.SetActive(ProfileManager.Instance.IsShowDebug());
        ShowPanelTotal();
        ShowPanelLoading();
#if UNITY_IOS
        // iOS 专属：请求 App Store 评分弹窗。
        // UnityEngine.iOS 命名空间只在 iOS 平台编译时存在，WebGL/Android 下会报 CS0234，必须条件编译。
        UnityEngine.iOS.Device.RequestStoreReview();
#endif

    }

    public bool isDoneFirstLoadPanel = false;
    bool isFirstLoad;
    public void FirstLoadPanel() {
        //LoadSceneManager.Instance.AddTotalProgress(30);
       
        isDoneFirstLoadPanel = true;
    }

    public void CloseAllPopUp(bool isFirstLoad = false) {
        isHasPopupOnScene = false;
        isHasShopPanel = false;
        foreach (KeyValuePair<UIPanelType, GameObject> panel in listPanel)
        {
            panel.Value.gameObject.SetActive(false);
        }
    }
    public bool IsHavePopUpOnScene() { return isHasPopupOnScene; }
    public bool IsHaveTutorial() { return isHasTutorial; }
    public void RegisterPanel(UIPanelType type, GameObject obj)
    {
        GameObject go = null;
        if (!listPanel.TryGetValue(type, out go))
        {
            //Debug.Log("RegisterPanel " + type.ToString());
            listPanel.Add(type, obj);
        }
        obj.SetActive(false);
    }
    public bool IsHavePanel(UIPanelType type) {
        GameObject panel = null;
        return listPanel.TryGetValue(type, out panel);
    }
    public GameObject GetPanel(UIPanelType type) {
        GameObject panel = null;
        if (!listPanel.TryGetValue(type, out panel)) {
            // 游戏 HUD（PanelPlayGame）与主界面容器（PanelTotal）留在底层，悬浮按钮显示在其上；
            // 其余弹窗统一放到 popupLayer，保证弹窗盖住侧边栏/激励按钮
            bool isHudPanel = (type == UIPanelType.PanelPlayGame) || (type == UIPanelType.PanelTotal);
            Transform parent = isHudPanel
                ? mainCanvas
                : (popupLayer != null ? popupLayer : mainCanvas);
            switch (type) {
                case UIPanelType.PanelBase:
                    panel = Instantiate(Resources.Load("UI/PanelBase") as GameObject, parent);
                    break;
                case UIPanelType.PanelTotal:
                    panel = Instantiate(Resources.Load("UI/PanelTotal") as GameObject, parent);
                    break;
                case UIPanelType.PanelSpin:
                    panel = Instantiate(Resources.Load("UI/PanelSpin") as GameObject, parent);
                    break;
                case UIPanelType.PanelDailyReward:
                    panel = Instantiate(Resources.Load("UI/PanelDailyReward") as GameObject, parent);
                    break;
                case UIPanelType.PanelItemsReward:
                    panel = Instantiate(Resources.Load("UI/PanelItemsReward") as GameObject, parent);
                    break;
                case UIPanelType.PanelBakery:
                    panel = Instantiate(Resources.Load("UI/PanelBakery") as GameObject, parent);
                    break;
                case UIPanelType.PanelPlayGame:
                    panel = Instantiate(Resources.Load("UI/PanelPlayGame") as GameObject, parent);
                    break;
                case UIPanelType.PanelSetting:
                    panel = Instantiate(Resources.Load("UI/PanelSetting") as GameObject, parent);
                    break;
                case UIPanelType.PanelDecorations:
                    panel = Instantiate(Resources.Load("UI/PanelDecorations") as GameObject, parent);
                    break;
                case UIPanelType.PanelCakeReward:
                    panel = Instantiate(Resources.Load("UI/PanelCakeReward") as GameObject, parent);
                    break;
                case UIPanelType.PanelLevelComplete:
                    panel = Instantiate(Resources.Load("UI/PanelLevelComplete") as GameObject, parent);
                    break;
                case UIPanelType.PanelLoading:
                    panel = Instantiate(Resources.Load("UI/PanelLoading") as GameObject, parent);
                    break;
                case UIPanelType.PanelShop:
                    panel = Instantiate(Resources.Load("UI/PanelShop") as GameObject, parent);
                    break;
                case UIPanelType.PanelUsingItem:
                    panel = Instantiate(Resources.Load("UI/PanelUsingItem") as GameObject, parent);
                    break;
                case UIPanelType.PanelLeaderBoard:
                    panel = Instantiate(Resources.Load("UI/PanelLeaderBoard") as GameObject, parent);
                    break;
                case UIPanelType.PanelTopUp:
                    panel = Instantiate(Resources.Load("UI/PanelTopUp") as GameObject, parent);
                    break;
                case UIPanelType.PanelQuickIAP:
                    panel = Instantiate(Resources.Load("UI/PanelQuickIAP") as GameObject, parent);
                    break;
                case UIPanelType.PanelSelectReward:
                    panel = Instantiate(Resources.Load("UI/PanelSelectReward") as GameObject, parent);
                    break;
                case UIPanelType.PanelHint:
                    panel = Instantiate(Resources.Load("UI/PanelHint") as GameObject, parent);
                    break;  
                case UIPanelType.PanelQuickTimeEvent:
                    panel = Instantiate(Resources.Load("UI/PanelQuickTimeEvent") as GameObject, parent);
                    break;
                case UIPanelType.PanelDailyQuest:
                    panel = Instantiate(Resources.Load("UI/PanelDailyQuest") as GameObject, parent);
                    break;
                case UIPanelType.PanelPreAds:
                    panel = Instantiate(Resources.Load("UI/PanelPreAds") as GameObject, parent);
                    break;
                case UIPanelType.PanelCheat:
                    panel = Instantiate(Resources.Load("UI/CheatPanel") as GameObject, parent);
                    break;
                case UIPanelType.PanelTutorial:
                    panel = Instantiate(Resources.Load("UI/PanelTutorial") as GameObject, parent);
                    break;
            }
            if (panel) panel.SetActive(true);
            return panel;
        }
        return listPanel[type];
    }

    public void OpenBlockAll() {
        panelTotal.OpenObjBlockAll();
    }

    public void CloseBlockAll()
    {
        panelTotal.CloseObjBlockAll();
    }

    public void ShowPanelBase()
    {
        GameObject go = GetPanel(UIPanelType.PanelBase);
        go.SetActive(true);
    }

    public void ClosePanelBase() {
        GameObject go = GetPanel(UIPanelType.PanelBase);
        go.SetActive(false);
    }

    public void ShowPanelTutorial()
    {
        GameObject go = GetPanel(UIPanelType.PanelTutorial);
        go.SetActive(true);
    }

    public void ClosePanelTutorial()
    {
        GameObject go = GetPanel(UIPanelType.PanelTutorial);
        go.SetActive(false);
        ShowInterstitialAd();
    }

    public void ShowPanelHint(ItemType itemType)
    {
        GameObject go = GetPanel(UIPanelType.PanelHint);
        go.SetActive(true);
        go.GetComponent<PanelHint>().ShowComponent(itemType);
        go.transform.SetAsLastSibling();
    }

    public void ClosePanelHint() {
        GameObject go = GetPanel(UIPanelType.PanelHint);
        go.SetActive(false);
    }

    public void ShowPanelTotal()
    {
        GameObject go = GetPanel(UIPanelType.PanelTotal);
        go.SetActive(true);
        if(panelTotal ==  null)
        {
            panelTotal = go.GetComponent<PanelTotal>();
        }
    }

    public void ClosePanelTotal()
    {
        GameObject go = GetPanel(UIPanelType.PanelTotal);
        go.SetActive(false);
    }
    public void ShowPanelTotalContent()
    {
        CloseOtherMenu(UIPanelType.PanelTotal);
        if (panelTotal == null)
        {
            GameObject go = GetPanel(UIPanelType.PanelTotal);
            go.SetActive(true);
            panelTotal = go.GetComponent<PanelTotal>();
        }
        panelTotal.ShowMainSceneContent(true);
    }

    public void ShowPanelPlayGame()
    {
        if (panelGamePlay == null)
        {
            GameObject go = GetPanel(UIPanelType.PanelPlayGame);
            panelGamePlay = go.GetComponent<PanelPlayGame>();
        }
        panelGamePlay.gameObject.SetActive(true);
        panelTotal.Transform.SetAsLastSibling();
    }
    public void ClosePanelPlayGame()
    {
        GameObject go = GetPanel(UIPanelType.PanelPlayGame);
        go.SetActive(false);
    }


    public void ShowPanelSpin()
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelSpin);
        go.SetActive(true);
        ShowInterstitialAd();

    }
    public void ClosePanelSpin()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelSpin);
        go.SetActive(false);
    }
    public void ShowPanelDailyReward()
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelDailyReward);
        go.SetActive(true);
    }
    public void ClosePanelDailyReward()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelDailyReward);
        go.SetActive(false);
        ShowInterstitialAd();

    }

    public void ShowPanelItemsReward()
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelItemsReward);
        go.SetActive(true);
    }
    public void ClosePanelItemsReward()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelItemsReward);
        go.SetActive(false);
    }

    public void ShowPanelBakery()
    {
        CloseOtherMenu(UIPanelType.PanelBakery);
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelBakery);
        go.SetActive(true);
        panelTotal.ShowMainSceneContent(false);
        panelTotal.Transform.SetAsLastSibling();
        if(panelBakery == null)
        {
            panelBakery = go.GetComponent<PanelBakery>();
        }
    }
    public void ClosePanelBakery()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelBakery);
        go.SetActive(false);
    }

    void CloseOtherMenu(UIPanelType ignorePanel)
    {
        if(panelBakery != null && ignorePanel != UIPanelType.PanelBakery)
        {
            if(panelBakery.gameObject.activeSelf)
            {
                panelBakery.OnClose();
            }
        }
        if (panelDecorations != null && ignorePanel != UIPanelType.PanelDecorations)
        {
            if (panelDecorations.gameObject.activeSelf)
            {
                panelDecorations.OnClose();
            }
        }
        if (panelShop != null && ignorePanel != UIPanelType.PanelShop)
        {
            if (panelShop.gameObject.activeSelf)
            {
                panelShop.OnClose();
            }
        }
        if (panelTopUp != null && ignorePanel != UIPanelType.PanelTopUp)
        {
            if (panelTopUp.gameObject.activeSelf)
            {
                panelTopUp.OnClose();
            }
        }
    }

    public void ShowPanelSetting()
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelSetting);
        go.SetActive(true);

        // 点击设置 → 展示插屏广告。
        // 抖音插屏是全屏原生广告，会盖在游戏画面之上；关闭后正好露出已经打开的设置面板，
        // 所以这里先打开面板再拉广告，广告关掉不会出现「面板还没准备好」的空档。
        ShowInterstitialAd();
    }
    public void ClosePanelSetting()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelSetting);
        go.SetActive(false);
    }

    public void ShowPanelDailyQuest()
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelDailyQuest);
        go.SetActive(true);
    }
    public void ClosePanelDailyQuest()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelDailyQuest);
        go.SetActive(false);
        ShowInterstitialAd();

    }

    public void ShowPanelDecorations()
    {
        CloseOtherMenu(UIPanelType.PanelDecorations);
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelDecorations);
        go.SetActive(true);
        panelTotal.ShowMainSceneContent(false);
        panelTotal.Transform.SetAsLastSibling();
        GameManager.Instance.decorationManager.StartCamera(true);
        if (panelDecorations == null)
        {
            panelDecorations = go.GetComponent<PanelDecorations>();
        }
    }
    public void ClosePanelDecorations()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelDecorations);
        go.SetActive(false);
        GameManager.Instance.decorationManager.StartCamera(false);
    }

    public void ShowPanelShop()
    {
        CloseOtherMenu(UIPanelType.PanelShop);
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelShop);
        go.SetActive(true);
        panelTotal.ShowMainSceneContent(false);
        panelTotal.Transform.SetAsLastSibling();
        if (panelShop == null)
        {
            panelShop = go.GetComponent<PanelShop>();
        }
    }
    public void ClosePanelShop()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelShop);
        go.SetActive(false);
    }

    public void ShowPanelCakeReward()
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelCakeReward);
        go.SetActive(true);
    }
    public void ClosePanelCakeReward()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelCakeReward);
        go.SetActive(false);
        ShowInterstitialAd();

    }
    PanelLevelComplete panelLevelComplete;
    public void ShowPanelLevelComplete(bool isWinGame)
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelLevelComplete);
        go.SetActive(true);
        if (panelLevelComplete == null) { panelLevelComplete = go.GetComponent<PanelLevelComplete>(); }
        panelLevelComplete.ShowPanel(isWinGame);
    }
    public void ClosePanelLevelComplete()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelLevelComplete);
        go.SetActive(false);
        ShowInterstitialAd();

    }

    public void ShowPanelLoading() {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelLoading);
        go.SetActive(true);
    }
    public void ClosePanelLoading() {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelLoading);
        go.SetActive(false);
    }

    public void ShowPanelUsingItem()
    {
        //isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelUsingItem);
        go.SetActive(true);
    }
    public void ClosePanelUsingItem()
    {
        //isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelUsingItem);
        go.SetActive(false);
    }

    public void ShowPanelLeaderBoard()
    {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelLeaderBoard);
        go.SetActive(true);
    }
    public void ClosePanelLeaderBoard()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelLeaderBoard);
        go.SetActive(false);
    }

    public void ShowPanelTopUp()
    {
        CloseOtherMenu(UIPanelType.PanelTopUp);
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelTopUp);
        go.SetActive(true);
        panelTotal.ShowMainSceneContent(false);
        panelTotal.Transform.SetAsLastSibling();
        if (panelTopUp == null)
        {
            panelTopUp = go.GetComponent<PanelTopUp>();
        }
    }

    public void ClosePanelTopUp()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelTopUp);
        go.SetActive(false);
    }

    public void ShowPanelQuickIAP(OfferID packageId)
    {
        GameObject go = GetPanel(UIPanelType.PanelQuickIAP);
        go.SetActive(true);
        go.GetComponent<PanelQuickIAP>().Init(packageId);
    }

    public void ClosePanelQuickIAP()
    {
        GameObject go = GetPanel(UIPanelType.PanelQuickIAP);
        go.transform.SetAsLastSibling();
        go.SetActive(false);
    }
    public void ShowPanelSelectReward()
    {
        Debug.Log("ShowPanelSelectReward");
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelSelectReward);
        go.SetActive(true);
    }
    public void ClosePanelSelectReward()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelSelectReward);
        go.SetActive(false);
        ShowInterstitialAd();

    }

    public void ShowPanelQuickTimeEvent() {
        isHasPopupOnScene = true;
        GameObject go = GetPanel(UIPanelType.PanelQuickTimeEvent);
        go.SetActive(true);
    }

    public void ClosePanelQuickTimeEvent()
    {
        isHasPopupOnScene = false;
        GameObject go = GetPanel(UIPanelType.PanelQuickTimeEvent);
        go.SetActive(false);
        ShowInterstitialAd();

    }

    public void ShowPanelPreAds() {
        if (ProfileManager.Instance.versionStatus == VersionStatus.Cheat) return;
        GameObject go = GetPanel(UIPanelType.PanelPreAds);
        go.SetActive(true);
    }

    public void ClosePanelPreAds()
    {
        GameObject go = GetPanel(UIPanelType.PanelPreAds);
        go.SetActive(false);
    }

    /// <summary>
    /// 展示插屏广告（统一走抖音小游戏广告平台）
    /// </summary>
    void ShowInterstitialAd()
    {
        AdManager adManager = AdManager.Instance;

        if (adManager == null)
        {
            // 正常流程由 LoadScene 里的 AdManager 负责且跨场景常驻；
            // 但直接在 SampleScene 里按 Play 调试时场景内没有它，
            // 这里补一个运行时实例，保证「点设置 → 插屏」这条链路在编辑器里也能验证。
            GameObject go = new GameObject("AdManager (Runtime)");
            adManager = go.AddComponent<AdManager>();
            Debug.Log("[广告] 场景中没有 AdManager，已创建运行时实例");
        }

        adManager.ShowInterstitialAd();
    }


}
