using System.Collections.Generic;
using System.IO;
using System.Text;
using TMPro;
using UnityEditor;
using UnityEngine;

/// <summary>
/// 兜底方案：用 Unity / TMP 自己的 API 重新烘焙中文字体资产，
/// 完全绕过手写 YAML 的结构风险。
///
/// 菜单：Tools/字体/重新烘焙中文字体资产（兜底）
///
/// 行为：
///   1. 读取现有字体资产里的全部字符（保持覆盖范围不变）
///   2. 再扫描所有 Prefab / 场景里的 TMP 文本，补齐字符
///   3. 用 TMP_FontAsset.CreateFontAsset 以 Static 模式重新烘焙
///   4. 写回同一路径（保留 .meta，guid 不变，40 处引用不断）
/// </summary>
public static class FontAssetRebake
{
    const string TargetAssetPath = "Assets/AdSDK/Font/DroidSansFallback SDF.asset";
    const int SamplingPointSize = 90;
    const int AtlasPadding = 9;
    const int AtlasSize = 2048;

    [MenuItem("Tools/字体/重新烘焙中文字体资产（兜底）")]
    public static void Rebake()
    {
        var old = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(TargetAssetPath);
        if (old == null)
        {
            Debug.LogError($"[字体] 找不到资产：{TargetAssetPath}");
            return;
        }

        // ---- 1. 收集字符集 ----
        var set = new HashSet<char>();
        if (old.characterTable != null)
        {
            foreach (var c in old.characterTable)
                if (c != null) set.Add((char)c.unicode);
        }
        int fromOld = set.Count;

        // ASCII 可见字符
        for (char c = ' '; c <= '~'; c++) set.Add(c);

        // 扫描所有 prefab / 场景中的 TMP 文本
        var guids = new List<string>();
        guids.AddRange(AssetDatabase.FindAssets("t:Prefab"));
        guids.AddRange(AssetDatabase.FindAssets("t:Scene"));
        foreach (var g in guids)
        {
            var path = AssetDatabase.GUIDToAssetPath(g);
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (go == null) continue;
            foreach (var t in go.GetComponentsInChildren<TMP_Text>(true))
            {
                if (string.IsNullOrEmpty(t.text)) continue;
                foreach (var ch in t.text) set.Add(ch);
            }
        }

        var chars = new List<char>(set);
        chars.RemoveAll(c => c < 32);
        Debug.Log($"[字体] 字符收集完成：原有 {fromOld}，合并后 {chars.Count}");

        // ---- 2. 找源 TTF ----
        Font src = null;
        if (old.sourceFontFile != null) src = old.sourceFontFile;
        if (src == null)
        {
            foreach (var guid in AssetDatabase.FindAssets("DroidSansFallback t:Font"))
            {
                src = AssetDatabase.LoadAssetAtPath<Font>(AssetDatabase.GUIDToAssetPath(guid));
                if (src != null) break;
            }
        }
        if (src == null)
        {
            Debug.LogError("[字体] 找不到源 TTF（DroidSansFallback），已中止。");
            return;
        }
        Debug.Log($"[字体] 源字体：{AssetDatabase.GetAssetPath(src)}");

        if (!EditorUtility.DisplayDialog("重新烘焙字体",
                $"将以 Static 模式重建 {Path.GetFileName(TargetAssetPath)}\n" +
                $"字符数 {chars.Count}，采样 {SamplingPointSize}pt，留白 {AtlasPadding}，图集 {AtlasSize}²\n\n" +
                "会覆盖当前资产（guid 不变，引用不受影响）。继续？", "开始", "取消"))
            return;

        try
        {
            AssetDatabase.StartAssetEditing();

            // ---- 3. 烘焙 ----
            var fa = TMP_FontAsset.CreateFontAsset(
                src,
                SamplingPointSize,
                AtlasPadding,
                UnityEngine.TextCore.LowLevel.GlyphRenderMode.SDFAA,
                AtlasSize,
                AtlasSize,
                AtlasPopulationMode.Static,
                true);

            if (fa == null)
            {
                Debug.LogError("[字体] CreateFontAsset 返回 null");
                return;
            }

            fa.name = Path.GetFileNameWithoutExtension(TargetAssetPath);

            // 逐批加入字符（Static 模式下一次不能太多，分批更稳）
            var sb = new StringBuilder();
            int added = 0, failed = 0;
            const int batch = 200;
            for (int i = 0; i < chars.Count; i += batch)
            {
                int n = Mathf.Min(batch, chars.Count - i);
                var part = chars.GetRange(i, n).ToArray();
                var s = new string(part);
                if (!fa.TryAddCharacters(s, out string missing))
                {
                    failed += (missing == null ? 0 : missing.Length);
                    if (!string.IsNullOrEmpty(missing)) sb.Append(missing);
                }
                added = fa.characterTable == null ? 0 : fa.characterTable.Count;
            }

            Debug.Log($"[字体] 烘焙完成：字符 {added}，缺失 {failed}" +
                      (sb.Length > 0 ? $"，缺失清单：{sb}" : ""));

            // ---- 4. 写回同一路径，图集与材质作为子对象并入 ----
            var tex0 = fa.atlasTextures;
            var mat = fa.material;
            AssetDatabase.CreateAsset(fa, TargetAssetPath);
            if (tex0 != null)
                foreach (var t in tex0)
                    if (t != null) AssetDatabase.AddObjectToAsset(t, fa);
            if (mat != null) AssetDatabase.AddObjectToAsset(mat, fa);

            EditorUtility.SetDirty(fa);
            AssetDatabase.SaveAssets();
        }
        finally
        {
            AssetDatabase.StopAssetEditing();
            AssetDatabase.Refresh();
        }

        var check = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(TargetAssetPath);
        if (check != null)
        {
            Debug.Log($"[字体] 结果：字符 {check.characterTable?.Count ?? 0}，" +
                      $"图集 {check.atlasTextures?.Length ?? 0} 张，" +
                      $"模式 {(int)check.atlasPopulationMode}（0=Static），" +
                      $"padding {check.atlasPadding}，gradientScale {check.material?.GetFloat("_GradientScale")}");
        }
        Debug.Log("[字体] 完成。请重新构建小游戏后在抖音开发者工具里验证。");
    }

    [MenuItem("Tools/字体/打印当前字体资产状态")]
    public static void DumpState()
    {
        var fa = AssetDatabase.LoadAssetAtPath<TMP_FontAsset>(TargetAssetPath);
        if (fa == null) { Debug.LogError("资产不存在"); return; }
        var mat = fa.material;
        Debug.Log($"[字体状态] 字符 {fa.characterTable?.Count ?? 0} / 字形 {fa.glyphTable?.Count ?? 0}\n" +
                  $"  图集数 {fa.atlasTextures?.Length ?? 0}，尺寸 {fa.atlasWidth}x{fa.atlasHeight}，padding {fa.atlasPadding}\n" +
                  $"  模式 {(int)fa.atlasPopulationMode}（0=Static 1=Dynamic），多图集 {fa.isMultiAtlasTexturesEnabled}\n" +
                  $"  图集索引 {fa.atlasTextureCount}\n" +
                  $"  _GradientScale {mat?.GetFloat("_GradientScale")} _ScaleRatioA {mat?.GetFloat("_ScaleRatioA")} " +
                  $"_ScaleRatioC {mat?.GetFloat("_ScaleRatioC")}\n" +
                  $"  _TextureWidth {mat?.GetFloat("_TextureWidth")} _TextureHeight {mat?.GetFloat("_TextureHeight")}\n" +
                  $"  _MainTex {(mat?.mainTexture != null ? mat.mainTexture.name : "null")}");
    }
}
