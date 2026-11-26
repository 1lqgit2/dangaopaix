using DG.Tweening.Core.Easing;
//using SDK;
using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;

public class GameManager : Singleton<GameManager>
{
    public bool playing = false;
    public CameraManager cameraManager;
    public AudioManager audioManager;
    public CakeManager cakeManager;
    public ObjectPooling objectPooling;
    public SpinManager spinManager;
    public DailyRewardManager dailyRewardManager;
    public DecorationManager decorationManager;
    public ItemManager itemManager;
    public LightManager lightManager;
    public QuestManager questManager;
    public QuickTimeEventManager quickTimeEventManager;
    [field: SerializeField] public TutorialManager tutorialManager { get; private set; }
    public List<ItemData> rewardItems;
    private void Start()
    {
        cameraManager.ShowARoom(0);
        AddTempName();
        ShowCollapsibleBanner();
    }
    public void PlayGame()
    {
        UIManager.instance.ShowPanelPlayGame();
        cakeManager.PlayGame();
        playing = true;
        if(ProfileManager.Instance.playerData.playerResourseSave.currentLevel == 0 )
        {
            tutorialManager.PlayTutorial();
        }
    }

    public void BackToMenu()
    {
        UIManager.instance.ClosePanelPlayGame();
        UIManager.instance.panelTotal.BackToMenu();
        cameraManager.ShowARoom(0);
        cameraManager.CloseMainCamera();
        playing = false;

        // playing 置为 false 之后才刷新，悬浮按钮才会重新出现在主菜单
        if (UIManager.instance.panelTotal != null)
        {
            UIManager.instance.panelTotal.RefreshFloatingButtons();
        }

        ShowCollapsibleBanner();
    }

    public float GetDefaultCakeProfit(int cakeID, int level, bool booster = false)
    {
        return (ConstantValue.VAL_DEFAULT_EXP + ConstantValue.VAL_DEFAULT_CAKE_ID * cakeID + ConstantValue.VAL_DEFAULT_CAKE_LEVEL * (level - 1))
            * (booster ? (ProfileManager.Instance.playerData.playerResourseSave.HasX2Booster() ? 2 : 1) : 1);
    }

    public void GetLevelUpReward(bool getLevelCake = true)
    {
        rewardItems.Clear();
        int level = ProfileManager.Instance.playerData.playerResourseSave.currentLevel;
        if(level == 1)
        {
            AddRewardByType(ItemType.Hammer);
        }
        else if (level == 2)
        {
            AddRewardByType(ItemType.FillUp);
        }
        else if (level == 3)
        {
            AddRewardByType(ItemType.ReRoll);
        }
        else
        {
            RandonReward();
        }
        //GetCakeOnLevelUp();
        //GetLevelUpItem();
        if(getLevelCake) 
            GetLevelCake();
        //CollectItemReward(rewardItems);
    }

    void GetLevelCake()
    {
        int level = ProfileManager.Instance.playerData.playerResourseSave.currentLevel;
        ItemData firstCake = new();
        firstCake.ItemType = ItemType.Cake;
        int newCakeID = ProfileManager.Instance.dataConfig.levelDataConfig.GetCakeID(level - 1);
        firstCake.amount = 1;
        if (newCakeID != -1)
        {
            ProfileManager.Instance.playerData.cakeSaveData.AddCake(newCakeID);
            ProfileManager.Instance.playerData.cakeSaveData.UseCake(newCakeID);
        }
        firstCake.subId = newCakeID;
        //rewardItems.Add(firstCake);
        AddItem(firstCake);
    }

    void AddRewardByType(ItemType type)
    {
        ItemData newItem = new();
        newItem.ItemType = type;
        newItem.subId = -1;
        switch (type)
        {
            case ItemType.Cake:
                newItem.amount = 5;
                ColectRewardCakeCard((int)newItem.amount);
                break;
            case ItemType.Swap:
            case ItemType.Hammer:
            case ItemType.ReRoll:
            case ItemType.Bomb:
            case ItemType.FillUp:
                newItem.amount = 1;
                break;
            default:
                break;
        }
        rewardItems.Add(newItem);
    }

    void ColectRewardCakeCard(int amount)
    {
        for (int i = 0; i < amount; i++)
        {
            int randonCake = ProfileManager.Instance.playerData.cakeSaveData.GetRandomUnlockedCake();
            ProfileManager.Instance.playerData.cakeSaveData.AddCakeCard(randonCake, 1);
        }
    }

//    [Button]
    public void CallTest(int testTime = 500)
    {
        StartCoroutine(TestRandonReward(testTime));
    }

    IEnumerator TestRandonReward(int testTime)
    {
        for (int i = 0; i < testTime; i++)
        {
            Debug.Log(i);
            yield return new WaitForSeconds(0.005f);
            RandonReward();
        }
    }

    public void RandonReward()
    {
        rewardItems.Clear();
        ProfileManager.Instance.dataConfig.itemDataConfig.InitRewardRandonList();
        for (int i = 0; i < 2; i++)
        {
            ItemData newItem = new();
            newItem.subId = -1;
            newItem.ItemType = ProfileManager.Instance.dataConfig.itemDataConfig.GetRewardItemOnLevel();
            while (CheckHasReward(newItem.ItemType))
            {
                newItem.ItemType = ProfileManager.Instance.dataConfig.itemDataConfig.GetRewardItemOnLevel();
            }
            ProfileManager.Instance.dataConfig.itemDataConfig.RemoveFromTemp(newItem.ItemType);

            if (newItem.ItemType == ItemType.Cake)
            {
                newItem.amount = UnityEngine.Random.Range(5, 10);
                int randonCake = ProfileManager.Instance.playerData.cakeSaveData.GetRandomUnlockedCake();
                newItem.subId = randonCake;
                //ColectRewardCakeCard((int)newItem.amount);
            }
            else if(newItem.ItemType == ItemType.Coin)
            {
                newItem.amount = (int)(UnityEngine.Random.Range(2, 8)) * 10;
            }
            else
            {
                //newItem.amount = UnityEngine.Random.Range(1, 5);
                newItem.amount = 1;
            }
            rewardItems.Add(newItem);
        }
    }

    bool CheckHasReward(ItemType itemType)
    {
        if(rewardItems == null || rewardItems.Count == 0)
            return false;
        for (int i = 0; i < rewardItems.Count; i++)
        {
            if (rewardItems[i].ItemType == itemType)
                return true;
        }
        return false;
    }

    void GetCakeOnLevelUp()
    {
        rewardItems.Clear();
        ItemData firstCake = new();
        firstCake.ItemType = ItemType.Cake;
        int newCakeID = ProfileManager.Instance.dataConfig.levelDataConfig.GetCakeID(ProfileManager.Instance.playerData.playerResourseSave.currentLevel - 1);
        firstCake.amount = UnityEngine.Random.Range(5, 10);
        if (newCakeID != -1)
        {
            ProfileManager.Instance.playerData.cakeSaveData.AddCake(newCakeID);
            ProfileManager.Instance.playerData.cakeSaveData.UseCake(newCakeID);
        }
        else
        {
            newCakeID = ProfileManager.Instance.dataConfig.cakeDataConfig.GetRandomCake();
        }
        firstCake.subId = newCakeID;
        int extraCakeId = ProfileManager.Instance.playerData.cakeSaveData.GetRandomUnlockedCake();
        while (extraCakeId == firstCake.subId)
        {
            extraCakeId = ProfileManager.Instance.playerData.cakeSaveData.GetRandomUnlockedCake();
        }
        ItemData extraCake = new();
        extraCake.ItemType = ItemType.Cake;
        extraCake.subId = extraCakeId;
        extraCake.amount = UnityEngine.Random.Range(5, 10);
        rewardItems.Add(firstCake);
        rewardItems.Add(extraCake);
    }

    public void GetItemRewards(List<ItemData> items)
    {
        rewardItems.Clear();
        for (int i = 0; i < items.Count; i++)
        {
            rewardItems.Add(items[i]);
            //AddItem(items[i]);
        }
        CollectItemReward(items);
    }

    void CollectItemReward(List<ItemData> items)
    {
        for (int i = 0; i < items.Count; i++)
        {
            AddItem(items[i]);
        }
        EventManager.TriggerEvent(EventName.AddItem.ToString());
    }

    public void AddItem(ItemData item)
    {
        if (item.ItemType != ItemType.Cake)
            ProfileManager.Instance.playerData.playerResourseSave.AddItem(item);
        else
            ProfileManager.Instance.playerData.cakeSaveData.AddCakeCard(item.subId, (int)item.amount);
    }

    public float GetItemAmount(ItemType itemType)
    {
        return ProfileManager.Instance.playerData.playerResourseSave.GetItemAmount(itemType);
    }

    public void ClearAllCake()
    {
        cakeManager.ClearAllCake();
    }

    List<string> tempName;
    void AddTempName()
    {
        tempName = new List<string>();
        tempName.Add("拉达戈");
        tempName.Add("弗雷");
        tempName.Add("玛丽卡");
        tempName.Add("格温");
        tempName.Add("玛莲");
        tempName.Add("米凯尔");
        tempName.Add("玛格");
        tempName.Add("古德里克");
        tempName.Add("莫戈");
        tempName.Add("兰丹");
        tempName.Add("拉妮");
        tempName.Add("理查德");
        tempName.Add("亚历山大");
        tempName.Add("帕奇");
    }

    public string GetRandomName()
    {
        return tempName[UnityEngine.Random.Range(0, tempName.Count)];
    }

    public void AddPiggySave(float amount)
    {
        ProfileManager.Instance.playerData.playerResourseSave.AddPiggySave(amount);
    }

    public bool IsHasNoAds()
    {
        if(ProfileManager.Instance.versionStatus == VersionStatus.Cheat) return true;
        return ProfileManager.Instance.playerData.playerResourseSave.IsHaveItem(ItemType.NoAds);
    }

    public void OnBuyPackSuccess(OfferID packageId)
    {
        switch (packageId)
        {
            case OfferID.None:
                break;
            case OfferID.pack1:
                rewardItems.Clear();
                ProfileManager.Instance.playerData.playerResourseSave.ClearPiggySave();
                ItemData itemData = new ItemData();
                itemData.ItemType = ItemType.Coin;
                itemData.amount = ProfileManager.Instance.playerData.playerResourseSave.piggySave;
                rewardItems.Add(itemData);
                CollectItemReward(rewardItems);
                break;
            case OfferID.piggy_pack:
                ShopPack shopPack = ProfileManager.Instance.dataConfig.shopDataConfig.GetShopPack(OfferID.piggy_pack);
                if(shopPack != null)
                {
                    GetItemRewards(shopPack.rewards);
                }
                break;
            default:
                break;
        }
    }

    public void ShowRewardVideo(WatchVideoRewardType watchVideoRewardType, UnityAction callBack)
    {
        // 已购买免广告：直接发奖
        if (IsHasNoAds())
        {
            Debug.Log($"[广告] 已拥有免广告特权，直接发放奖励（{watchVideoRewardType}）");
            GrantRewardAd(callBack);
            return;
        }

        if (AdManager.Instance == null)
        {
#if UNITY_EDITOR
            // 编辑器里场景可能没挂 AdManager，直接发奖，避免调试时卡住
            Debug.LogWarning($"[广告] 场景里没有 AdManager，编辑器下直接发放奖励（{watchVideoRewardType}）");
            GrantRewardAd(callBack);
#else
            Debug.LogError("[广告] 场景中没有 AdManager，无法播放激励视频");
            AdConfirm.ShowAdError();
#endif
            return;
        }

        // 激励视频统一走抖音小游戏广告平台：
        // 真机上只有播放完成才回调发奖；编辑器里 AdManager 会模拟「播放完成」，
        // 这样「看广告领奖励」的入口在 Unity 里也能完整跑通。
        Debug.Log($"[广告] 发起激励视频请求（{watchVideoRewardType}）");
        AdManager.Instance.ShowRewardedVideoAd(
            () =>
            {
                Debug.Log($"[广告] 激励视频完成，发放奖励（{watchVideoRewardType}）");
                GrantRewardAd(callBack);
            },
            (error) =>
            {
                Debug.LogError($"[广告] 激励视频未完成或播放失败：{error}（{watchVideoRewardType}）");
                AdConfirm.ShowAdError();
            });
    }

    /// <summary>
    /// 看完广告后的统一发奖入口。
    /// 顺序很关键：先把奖励发给玩家，再记任务进度。
    /// 之前是「先记任务进度再发奖」，任务数据一旦异常就会把玩家看完广告换来的奖励吞掉。
    /// </summary>
    void GrantRewardAd(UnityAction callBack)
    {
        // 1. 先发奖励（玩家真正拿到东西）
        if (callBack != null)
        {
            try
            {
                callBack();
                Debug.Log("[广告] 奖励已发放");
            }
            catch (Exception e)
            {
                Debug.LogError($"[广告] 发奖回调执行异常：{e}");
            }
        }
        else
        {
            Debug.LogWarning("[广告] 发奖回调为空，奖励可能没有真正发出");
        }

        // 2. 再记任务进度，这一步失败不能影响已经发出去的奖励
        try
        {
            if (questManager != null)
                questManager.AddProgress(QuestType.CompleteCake, 1);
        }
        catch (Exception e)
        {
            Debug.LogWarning($"[广告] 记录任务进度失败（不影响发奖）：{e.Message}");
        }
    }

    public void ShowCollapsibleBanner()
    {
        // 抖音小游戏没有 Banner / 可折叠 Banner，保持空实现
    }

    public void ShowInterRest()
    {
        if (IsHasNoAds()) return;
        if (ProfileManager.Instance.playerData.playerResourseSave.currentLevel >= 3)
            UIManager.instance.ShowPanelPreAds();
    }

    public void ShowInter()
    {
        if (GameManager.Instance.IsHasNoAds()) return;
        if (ProfileManager.Instance.versionStatus == VersionStatus.Cheat) return;
        // 插屏广告统一走抖音小游戏广告平台
        if (AdManager.Instance != null)
            AdManager.Instance.ShowInterstitialAd();
    }
}

public enum WatchVideoRewardType
{
    NONE,
    X2CLAIM,
    UNLOCKITEM,
    TEST_ADS,
    GetFreeBooster,
    FreeCoinAds,
    X2RewardAds,
    CollectCoinAds,
    BoosterPlayTime,
    TimeBooster,
    UpgradeCake,
    GameOverRevive,
    FreeSpinAds,
    GetExtraCard,
}