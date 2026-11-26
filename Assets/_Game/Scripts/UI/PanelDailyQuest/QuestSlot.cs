using DG.Tweening;
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class QuestSlot : MonoBehaviour
{
    public int slotIndex;
    [SerializeField] QuestType questType;
    [SerializeField] Button collectBtn;
    [SerializeField] TextMeshProUGUI txtName;
    [SerializeField] TextMeshProUGUI txtProgress;
    [SerializeField] TextMeshProUGUI txtRewardAmount;
    [SerializeField] Slider sProgress;
    [SerializeField] GameObject objSlider;
    float currentProgress;
    float questRequire;

    private void Start()
    {
        collectBtn.onClick.AddListener(CollectQuest);
    }
    public void InitData(QuestType questType)
    {
        this.questType = questType;
        ReInit();
    }

    private void OnEnable()
    {
        ReScale();
        ReInit();
    }

    void ReInit()
    {
        txtRewardAmount.text = ConstantValue.VAL_QUEST_COIN.ToString();
        currentProgress = ProfileManager.Instance.playerData.questDataSave.GetCurrentProgress(questType);
        questRequire = ProfileManager.Instance.playerData.questDataSave.GetCurrentRequire(questType);
        collectBtn.interactable = (currentProgress >= questRequire);

        txtProgress.text = currentProgress.ToString() + ConstantValue.STR_SLASH + questRequire;
        if (currentProgress > questRequire)
            currentProgress = questRequire;
        sProgress.maxValue = questRequire;
        sProgress.value = currentProgress;
        SetName();
    }

    void SetName()
    {
        switch (questType)
        {
            case QuestType.None:
                break;
            case QuestType.WatchADS:
                txtName.text = "观看 " + questRequire.ToString() + " 次广告";
                break;
            case QuestType.CompleteCake:
                txtName.text = "完成 " + questRequire.ToString() + " 个蛋糕";
                break;
            case QuestType.UseBooster:
                txtName.text = "使用 " + questRequire.ToString() + " 个道具";
                break;
            default:
                break;
        }
    }

    public void ReScale()
    {
        transform.DOScale(1, 0.25f).From(0).SetDelay(0.25f + 0.1f * slotIndex);
    }

    void CollectQuest()
    {
        GameManager.Instance.questManager.ClaimQuest(questType);
        ReInit();
        ReScale();

    }
}
