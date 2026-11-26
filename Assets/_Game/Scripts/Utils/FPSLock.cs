using UnityEngine;

/// <summary>
/// 锁定目标帧率。
/// 注意：小游戏（WebGL）里 Screen.currentResolution 不可靠——返回的 refreshRate 可能是
/// 宿主上报的固定值（常见 60/120），直接拿来用会把目标帧率设到设备撑不住的高度，
/// 结果就是持续掉帧、抖动，审核会判"运行卡顿"。这里固定 60，并配 vsync=0 一起使用。
/// </summary>
public class FPSLock : MonoBehaviour
{
    /// <summary>目标帧率。抖音小游戏建议 60；低端机若仍卡可降到 30。</summary>
    [SerializeField] int targetFPS = 60;

    void Awake()
    {
        Apply();
    }

    void OnEnable()
    {
        Apply();
    }

    void Apply()
    {
        // vSync 只能靠 QualitySettings 关；关掉后 targetFrameRate 才真正生效。
        QualitySettings.vSyncCount = 0;

        int fps = this.targetFPS > 0 ? this.targetFPS : 60;

#if UNITY_WEBGL && !UNITY_EDITOR
        // 小游戏真机的 Screen.currentResolution 不可信，最多用到 60，避免出现 120 之类的畸高值
        fps = Mathf.Min(fps, 60);
#endif

        Application.targetFrameRate = fps;
    }
}
