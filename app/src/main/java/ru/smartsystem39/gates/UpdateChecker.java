package ru.smartsystem39.gates;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Проверка обновлений через GitHub Releases. */
public final class UpdateChecker {

    public static final String REPO = "vitosamin/vorota";
    public static final String API_URL = "https://api.github.com/repos/" + REPO + "/releases/latest";

    public static class Info {
        public final String tag;
        public final String notes;
        public final String apkUrl;
        public final boolean newer;
        public final String error;

        private Info(String tag, String notes, String apkUrl, boolean newer, String error) {
            this.tag = tag;
            this.notes = notes;
            this.apkUrl = apkUrl;
            this.newer = newer;
            this.error = error;
        }

        static Info err(String error) {
            return new Info("", "", "", false, error);
        }
    }

    private UpdateChecker() {}

    public static Info check(String currentVersion) {
        Http.Response r = Http.get(API_URL, null, false);
        if (!r.ok()) {
            String reason = r.code == 403 ? "превышен лимит запросов GitHub"
                    : (r.error == null ? "HTTP " + r.code : r.error);
            return Info.err(reason);
        }
        try {
            JSONObject release = new JSONObject(r.body);
            String tag = release.optString("tag_name", "");
            if (tag.isEmpty()) return Info.err("в релизе нет тега");
            String apkUrl = "";
            JSONArray assets = release.optJSONArray("assets");
            if (assets != null) {
                for (int i = 0; i < assets.length(); i++) {
                    JSONObject asset = assets.getJSONObject(i);
                    if (asset.optString("name", "").toLowerCase().endsWith(".apk")) {
                        apkUrl = asset.optString("browser_download_url", "");
                        if (!apkUrl.isEmpty()) break;
                    }
                }
            }
            if (apkUrl.isEmpty()) return Info.err("в релизе нет APK");
            return new Info(tag, release.optString("body", ""), apkUrl,
                    isNewer(currentVersion, tag), null);
        } catch (Exception e) {
            return Info.err("некорректный ответ GitHub");
        }
    }

    public static String download(String url, File out) {
        Http.Response r = Http.download(url, out, false);
        if (!r.ok()) return r.error == null ? "ошибка скачивания" : r.error;
        return null;
    }

    static boolean isNewer(String current, String tag) {
        int[] c = versionParts(current);
        int[] n = versionParts(tag);
        int len = Math.max(c.length, n.length);
        for (int i = 0; i < len; i++) {
            int a = i < c.length ? c[i] : 0;
            int b = i < n.length ? n[i] : 0;
            if (a != b) return b > a;
        }
        return false;
    }

    private static int[] versionParts(String version) {
        if (version == null) return new int[0];
        String s = version.trim();
        if (s.startsWith("v") || s.startsWith("V")) s = s.substring(1);
        String[] parts = s.split("\\.");
        int[] out = new int[parts.length];
        for (int i = 0; i < parts.length; i++) {
            Matcher m = Pattern.compile("^(\\d+)").matcher(parts[i]);
            out[i] = m.find() ? Integer.parseInt(m.group(1)) : 0;
        }
        return out;
    }
}
