package ru.smartsystem39.gates;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ConnectException;
import java.net.HttpURLConnection;
import java.net.SocketTimeoutException;
import java.net.URL;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;

import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLException;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/** Минимальный HTTP-клиент без сторонних библиотек. */
public final class Http {

    private static final String USER_AGENT = "Vorota/1.0 (Android)";

    public static final class Response {
        public int code;
        public String body = "";
        public String error;

        public boolean ok() {
            return error == null && code >= 200 && code < 300;
        }
    }

    private Http() {}

    public static Response get(String url, String token, boolean insecure) {
        return request("GET", url, token, null, insecure);
    }

    public static Response post(String url, String token, String json, boolean insecure) {
        return request("POST", url, token, json, insecure);
    }

    private static Response request(String method, String url, String token, String json, boolean insecure) {
        Response r = new Response();
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            if (insecure && conn instanceof HttpsURLConnection) {
                allowAll((HttpsURLConnection) conn);
            }
            conn.setRequestMethod(method);
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(9000);
            conn.setInstanceFollowRedirects(true);
            conn.setUseCaches(false);
            conn.setRequestProperty("Accept", "application/json, text/plain, */*");
            conn.setRequestProperty("User-Agent", USER_AGENT);
            if (token != null && !token.isEmpty()) {
                conn.setRequestProperty("Authorization", "Bearer " + token);
            }
            if (json != null) {
                byte[] bytes = json.getBytes(StandardCharsets.UTF_8);
                conn.setDoOutput(true);
                conn.setFixedLengthStreamingMode(bytes.length);
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                OutputStream os = conn.getOutputStream();
                os.write(bytes);
                os.close();
            }
            r.code = conn.getResponseCode();
            InputStream is = r.code >= 400 ? conn.getErrorStream() : conn.getInputStream();
            r.body = read(is);
            if (r.code < 200 || r.code >= 300) {
                r.error = "HTTP " + r.code;
            }
        } catch (SocketTimeoutException e) {
            r.error = "Таймаут соединения";
        } catch (UnknownHostException e) {
            r.error = "Хост не найден";
        } catch (ConnectException e) {
            r.error = "Нет соединения";
        } catch (SSLException e) {
            r.error = "Ошибка HTTPS: " + safeMessage(e);
        } catch (Exception e) {
            r.error = safeMessage(e);
        } finally {
            if (conn != null) conn.disconnect();
        }
        return r;
    }

    /** Скачивает URL в файл; возвращает error == null при успехе. */
    public static Response download(String url, File out, boolean insecure) {
        Response r = new Response();
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            if (insecure && conn instanceof HttpsURLConnection) {
                allowAll((HttpsURLConnection) conn);
            }
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(30000);
            conn.setInstanceFollowRedirects(true);
            conn.setUseCaches(false);
            conn.setRequestProperty("User-Agent", USER_AGENT);
            conn.setRequestProperty("Accept", "application/octet-stream");
            r.code = conn.getResponseCode();
            if (r.code < 200 || r.code >= 300) {
                r.error = "HTTP " + r.code;
                return r;
            }
            File parent = out.getParentFile();
            if (parent != null && !parent.exists()) parent.mkdirs();
            InputStream is = conn.getInputStream();
            FileOutputStream fos = new FileOutputStream(out);
            byte[] buf = new byte[16384];
            int n;
            long total = 0;
            while ((n = is.read(buf)) > 0) {
                fos.write(buf, 0, n);
                total += n;
            }
            fos.flush();
            fos.close();
            is.close();
            if (total <= 0) r.error = "Пустой файл";
            r.body = String.valueOf(total);
        } catch (SocketTimeoutException e) {
            r.error = "Таймаут соединения";
        } catch (UnknownHostException e) {
            r.error = "Хост не найден";
        } catch (ConnectException e) {
            r.error = "Нет соединения";
        } catch (SSLException e) {
            r.error = "Ошибка HTTPS: " + safeMessage(e);
        } catch (Exception e) {
            r.error = safeMessage(e);
        } finally {
            if (conn != null) conn.disconnect();
        }
        return r;
    }

    private static String read(InputStream is) throws Exception {
        if (is == null) return "";
        StringBuilder sb = new StringBuilder();
        BufferedReader br = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
        String line;
        while ((line = br.readLine()) != null) sb.append(line).append('\n');
        br.close();
        return sb.toString().trim();
    }

    private static String safeMessage(Exception e) {
        String m = e.getMessage();
        return m == null || m.trim().isEmpty() ? e.getClass().getSimpleName() : m;
    }

    private static void allowAll(HttpsURLConnection conn) throws Exception {
        SSLContext ctx = SSLContext.getInstance("TLS");
        ctx.init(null, new TrustManager[]{new X509TrustManager() {
            @Override public void checkClientTrusted(java.security.cert.X509Certificate[] chain, String authType) {}
            @Override public void checkServerTrusted(java.security.cert.X509Certificate[] chain, String authType) {}
            @Override public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                return new java.security.cert.X509Certificate[0];
            }
        }}, new java.security.SecureRandom());
        conn.setSSLSocketFactory(ctx.getSocketFactory());
        conn.setHostnameVerifier((hostname, session) -> true);
    }
}
