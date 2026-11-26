using DG.Tweening;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class PanelItemsReward : UIPanel
{
    [SerializeField] Transform titleTrs;
    [SerializeField] Button closeBtn;
    [SerializeField] RewardItemUI itemUIPrefab;
    [SerializeField] Transform rewardItemUIsContainer;
    List<RewardItemUI> rewardItemUIs;
    List<ItemData> rewards;
    int spawnedCount;
    public Transform coinBar;
    public Transform bagBar;

    Vector3 titleScale = new Vector3 (0f, 1f, 1f);
    public override void Awake()
    {
        panelType = UIPanelType.PanelItemsReward;
        base.Awake();
        titleTrs.localScale = titleScale;
        rewardItemUIs = new List<RewardItemUI>();
    }

    private void Start()
    {
        closeBtn.onClick.AddListener(ClosePanel);
    }

    private void OnEnable()
    {
        StopAllCoroutines();
        titleTrs.DOScaleX(1, 0.25f);
        DisableOldItem();
        InitReward();
        transform.SetAsLastSibling();
        coinBar.DOScale(1, 0.25f).From(0).SetDelay(2);
        bagBar.DOScale(1, 0.25f).From(0).SetDelay(2);
    }

    void InitReward()
    {
        closeBtn.interactable = false;
        spawnedCount = 0;
        rewards = GameManager.Instance != null ? GameManager.Instance.rewardItems : null;

        // 奖励列表为空时，物品动画永远不会结束，关闭按钮会一直锁着，
        // 玩家会以为「奖励领不到、弹窗也关不掉」。这里直接放行。
        if (rewards == null || rewards.Count == 0)
        {
            Debug.LogWarning("[奖励弹窗] 奖励列表为空，直接解锁关闭按钮");
            closeBtn.interactable = true;
            return;
        }

        StartCoroutine(SpawnReward());
        StartCoroutine(UnlockCloseFallback());
    }

    /// <summary>
    /// 兜底：物品动画协程如果因为异常中断，6 秒后强制解锁关闭按钮，
    /// 避免奖励弹窗把玩家卡住（用 unscaled 时间，广告期间 timeScale=0 也生效）。
    /// </summary>
    IEnumerator UnlockCloseFallback()
    {
        yield return new WaitForSecondsRealtime(6f);

        if (closeBtn != null && !closeBtn.interactable)
        {
            Debug.LogWarning("[奖励弹窗] 奖励动画超时，强制解锁关闭按钮");
            closeBtn.interactable = true;
        }
    }

    IEnumerator SpawnReward()
    {
        yield return ConstantValue.WAIT_SEC01;
        if (spawnedCount < rewards.Count)
        {
            RewardItemUI rewardItemUI = GetRewardItemUI();
            rewardItemUI.Init(rewards[spawnedCount], this);
            spawnedCount++;
            StartCoroutine(SpawnReward());
        }
        else
        {
            yield return ConstantValue.WAIT_SEC1;
            yield return ConstantValue.WAIT_SEC1;
            yield return ConstantValue.WAIT_SEC1;
            closeBtn.interactable = true;
        }
    }

    RewardItemUI GetRewardItemUI()
    {
        for (int i = 0; i < rewardItemUIs.Count; i++)
        {
            if (!rewardItemUIs[i].gameObject.activeSelf)
            {
                rewardItemUIs[i].gameObject.SetActive(true);
                return rewardItemUIs[i];
            }
        }
        RewardItemUI newRewardItemUI = Instantiate(itemUIPrefab, rewardItemUIsContainer);
        rewardItemUIs.Add(newRewardItemUI);
        return newRewardItemUI;
    }

    void DisableOldItem()
    {
        for (int i = 0; i < rewardItemUIs.Count; i++)
        {
            rewardItemUIs[i].gameObject.SetActive(false);
        }
    }

    void ClosePanel()
    {
        GameManager.Instance.audioManager.PlaySoundEffect(SoundId.SFX_UIButton);
        for (int i = 0; i < rewardItemUIs.Count; i++)
        {
            rewardItemUIs[i].gameObject.SetActive(false);
        }
        titleTrs.localScale = titleScale;
        UIManager.instance.ClosePanelItemsReward();
        //if (GameManager.Instance.cakeManager.justUnlockedCake != -1 && GameManager.Instance.cakeManager.justUnlockedCake != 0)
        //{
        //    UIManager.instance.ShowPanelCakeReward();
        //}
        //else if(GameManager.Instance.cakeManager.levelUp)
        //{
        //    GameManager.Instance.cakeManager.cakeShowComponent.ShowNormalCake();
        //    GameManager.Instance.cakeManager.cakeShowComponent.ShowNextToUnlockCake();
        //    GameManager.Instance.cakeManager.ClearAllCake();
        //    GameManager.Instance.cakeManager.SetOnMove(false);
        //    UIManager.instance.ShowPanelLoading();
        //}
    }
}
