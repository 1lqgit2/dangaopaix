using UnityEngine;

/// <summary>
/// 本地推送通知管理器的占位实现。
///
/// 历史原因：本文件曾被清空为 0 字节，但 LoadScene 中仍保留了挂载该脚本的
/// PushNotificationManager 节点，导致打包时出现
/// "Script attached to 'PushNotificationManager' in scene '' is missing!" 警告。
///
/// 当前项目目标平台为抖音小游戏（WebGL），平台本身不提供本地定时推送能力，
/// 因此这里只保留类型以维持场景引用完整，不实现任何通知逻辑。
/// </summary>
public class PushNotificationManager : MonoBehaviour
{
    private static PushNotificationManager instance;

    /// <summary>全局单例，便于后续需要时接入（可能为 null）。</summary>
    public static PushNotificationManager Instance
    {
        get { return instance; }
    }

    private void Awake()
    {
        if (instance != null && instance != this)
        {
            Destroy(gameObject);
            return;
        }

        instance = this;
    }

    private void OnDestroy()
    {
        if (instance == this)
        {
            instance = null;
        }
    }

    /// <summary>取消所有已注册的本地通知（当前平台无实现，保留接口）。</summary>
    public void CancelAll()
    {
    }

    /// <summary>请求通知权限（当前平台无实现，保留接口）。</summary>
    public void RequestPermission()
    {
    }
}
