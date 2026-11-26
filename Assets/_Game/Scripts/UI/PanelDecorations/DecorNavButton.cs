using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class DecorNavButton : MonoBehaviour
{
    [SerializeField] Button navBtn;
    [SerializeField] TextMeshProUGUI navTxt;
    [SerializeField] DecorationType decorationType;
    [SerializeField] PanelDecorations panelDecorations;
    [SerializeField] Color activeColor;
    [SerializeField] Color deactiveColor;
    void Start()
    {
        navBtn.onClick.AddListener(NavBtnOnClick);
        navTxt.text = GetDecorationName(decorationType);
    }

    string GetDecorationName(DecorationType type)
    {
        switch (type)
        {
            case DecorationType.Table:
                return "桌子";
            case DecorationType.Plate:
                return "盘子";
            case DecorationType.Floor:
                return "地板";
            case DecorationType.Effect:
                return "特效";
            default:
                return "装饰";
        }
    }

    void NavBtnOnClick()
    {
        GameManager.Instance.audioManager.PlaySoundEffect(SoundId.SFX_UIButton);
        panelDecorations.InitDecorationData(decorationType);
        panelDecorations.SetSelectedNavBtn(this);
        SelectBtn(true);
    }

    public void SelectBtn(bool select)
    {
        navTxt.color = select ? activeColor : deactiveColor;
    }

}
