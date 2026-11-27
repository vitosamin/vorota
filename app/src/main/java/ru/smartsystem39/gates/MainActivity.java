package ru.smartsystem39.gates;

import android.animation.Keyframe;
import android.animation.ObjectAnimator;
import android.animation.PropertyValuesHolder;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.res.Configuration;
import android.graphics.Color;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.Network;
import android.net.Uri;
import java.net.Inet4Address;
import java.net.InetAddress;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextUtils;
import android.text.TextWatcher;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends Activity {

    private Config cfg;
    private ExecutorService io;
    private final Handler ui = new Handler(Looper.getMainLooper());

    private List<Device> devices = new ArrayList<>();
    private final Map<String, List<Card>> cards = new HashMap<>();
    private ExecutorService commands;
    private static final AtomicBoolean commandInFlight = new AtomicBoolean(false);
    private final Map<String, Status> lastStatus = new HashMap<>();
    private final AtomicBoolean inFlight = new AtomicBoolean(false);
    private boolean polling = false;
    private int devicesRevision = 0;
    private boolean allExpanded = false;
    private int tab = 0;

    private ScrollView scrollMain;
    private ScrollView scrollSettings;
    private LinearLayout listMain;
    private LinearLayout deviceSettings;
    private LinearLayout statusChip;
    private TextView headerTitle;
    private TextView statusText;
    private TextView testResult;
    private TextView versionText;
    private TextView updateStatus;
    private Button btnCheckUpdates;
    private Button btnInstallUpdate;
    private String pendingApkUrl;
    private boolean checkingUpdates = false;
    private boolean downloadingUpdate = false;
    private boolean importingGate = false;
    private boolean gateKeyPromptShown = false;
    private View statusDot;
    private static final long PULSE_PERIOD = 4200;
    private ObjectAnimator pulse;
    private ValueAnimator cardPulse;
    private ImageButton btnRefresh;
    private EditText haUrl;
    private EditText haToken;
    private EditText gateUrl;
    private EditText gateLocalUrl;
    private EditText gateToken;
    private Button btnGateImport;
    private TextView gateStatus;
    private CheckBox haInsecure;
    private CheckBox pultUi;
    private WebView pultWeb;
    private boolean pultWebReady = false;
    private boolean pultWebFailed = false;
    private boolean pultSheetOpen = false;
    private Button btnTest;
    private Button btnAddDevice;
    private LinearLayout navDevices;
    private LinearLayout navSettings;
    private ImageView navDevicesIcon;
    private ImageView navSettingsIcon;
    private TextView navDevicesText;
    private TextView navSettingsText;

    private static final class Card {
        String id;
        Device device;
        LinearLayout root;
        TextView name;
        TextView status;
        LinearLayout pill;
        View dot;
        Button action;
        ImageView icon;
        boolean live;
        boolean stacked;
    }

    @Override
    protected void attachBaseContext(Context base) {
        int mode = new Config(base).getThemeMode();
        if (mode != 0) {
            android.content.res.Configuration conf =
                    new android.content.res.Configuration(base.getResources().getConfiguration());
            conf.uiMode = (conf.uiMode & ~android.content.res.Configuration.UI_MODE_NIGHT_MASK)
                    | (mode == 2 ? android.content.res.Configuration.UI_MODE_NIGHT_YES
                                 : android.content.res.Configuration.UI_MODE_NIGHT_NO);
            base = base.createConfigurationContext(conf);
        }
        super.attachBaseContext(base);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        cfg = new Config(this);
        // 3.17: один раз включаем веб-«Пульт», даже если 3.16 успела откатиться
        // в классический вид. Дальше решение пользователя не перетираем.
        if (cfg.getUiVersion() < 1) {
            cfg.setPultUi(true);
            cfg.setUiVersion(1);
        }
        io = Executors.newSingleThreadExecutor();
        commands = Executors.newSingleThreadExecutor();
        setContentView(R.layout.activity_main);
        bind();
        setupSettings();
        setupNav();
        if (cfg.pultUi()) ensurePultWeb();
        reloadDevices();
        selectTab(0);
        ui.postDelayed(() -> checkUpdates(true), 1500);
        ui.postDelayed(this::autoImportGate, 900);
        ui.postDelayed(this::askGateKeyIfNeeded, 600);
    }

    private void bind() {
        scrollMain = findViewById(R.id.scrollMain);
        scrollSettings = findViewById(R.id.scrollSettings);
        listMain = findViewById(R.id.listMain);
        deviceSettings = findViewById(R.id.deviceSettings);
        statusChip = findViewById(R.id.statusChip);
        headerTitle = findViewById(R.id.headerTitle);
        statusText = findViewById(R.id.statusText);
        testResult = findViewById(R.id.testResult);
        statusDot = findViewById(R.id.statusDot);
        btnRefresh = findViewById(R.id.btnRefresh);
        haUrl = findViewById(R.id.haUrl);
        haToken = findViewById(R.id.haToken);
        gateUrl = findViewById(R.id.gateUrl);
        gateLocalUrl = findViewById(R.id.gateLocalUrl);
        gateToken = findViewById(R.id.gateToken);
        btnGateImport = findViewById(R.id.btnGateImport);
        gateStatus = findViewById(R.id.gateStatus);
        haInsecure = findViewById(R.id.haInsecure);
        pultUi = findViewById(R.id.pultUi);
        btnTest = findViewById(R.id.btnTest);
        btnAddDevice = findViewById(R.id.btnAddDevice);
        versionText = findViewById(R.id.versionText);
        updateStatus = findViewById(R.id.updateStatus);
        btnCheckUpdates = findViewById(R.id.btnCheckUpdates);
        btnInstallUpdate = findViewById(R.id.btnInstallUpdate);
        themeLight = findViewById(R.id.themeLight);
        themeDark = findViewById(R.id.themeDark);
        themeSystem = findViewById(R.id.themeSystem);
        themeLight.setOnClickListener(v -> applyTheme(1));
        themeDark.setOnClickListener(v -> applyTheme(2));
        themeSystem.setOnClickListener(v -> applyTheme(0));
        navDevices = findViewById(R.id.navDevices);
        navSettings = findViewById(R.id.navSettings);
        navDevicesIcon = findViewById(R.id.navDevicesIcon);
        navSettingsIcon = findViewById(R.id.navSettingsIcon);
        navDevicesText = findViewById(R.id.navDevicesText);
        navSettingsText = findViewById(R.id.navSettingsText);
    }

    private void setupSettings() {
        haUrl.setText(cfg.getHaUrl());
        haToken.setText(cfg.getHaToken());
        haInsecure.setChecked(cfg.haInsecure());

        haUrl.addTextChangedListener(new SimpleWatcher() {
            @Override
            public void afterTextChanged(Editable s) {
                cfg.setHaUrl(s.toString().trim());
            }
        });
        haToken.addTextChangedListener(new SimpleWatcher() {
            @Override
            public void afterTextChanged(Editable s) {
                cfg.setHaToken(s.toString().trim());
            }
        });
        haInsecure.setOnCheckedChangeListener((buttonView, isChecked) -> cfg.setHaInsecure(isChecked));

        pultUi.setChecked(cfg.pultUi());
        pultUi.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (cfg.pultUi() == isChecked) return;
            cfg.setPultUi(isChecked);
            toast(getString(isChecked ? R.string.pult_on : R.string.pult_off));
            rebuildMain();
            selectTab(0);
        });

        gateUrl.setText(cfg.getGateUrl());
        gateLocalUrl.setText(cfg.getGateLocalUrl());
        gateToken.setText(cfg.getGateToken());
        gateUrl.addTextChangedListener(new SimpleWatcher() {
            @Override
            public void afterTextChanged(Editable s) {
                cfg.setGateUrl(s.toString().trim());
            }
        });
        gateLocalUrl.addTextChangedListener(new SimpleWatcher() {
            @Override
            public void afterTextChanged(Editable s) {
                cfg.setGateLocalUrl(s.toString().trim());
            }
        });
        gateToken.addTextChangedListener(new SimpleWatcher() {
            @Override
            public void afterTextChanged(Editable s) {
                cfg.setGateToken(s.toString().trim());
            }
        });
        btnGateImport.setOnClickListener(v -> importGateDoors());

        btnTest.setOnClickListener(v -> testConnection());
        btnAddDevice.setOnClickListener(v -> openEditor(null));
        btnRefresh.setOnClickListener(v -> pollOnce());

        versionText.setText(getString(R.string.version_fmt, appVersion()));
        updateStatus.setText(R.string.update_checking);
        btnCheckUpdates.setOnClickListener(v -> checkUpdates(false));
        btnInstallUpdate.setOnClickListener(v -> {
            if (pendingApkUrl != null && !pendingApkUrl.isEmpty()) {
                downloadAndInstall(pendingApkUrl);
            }
        });
    }

    private void setupNav() {
        navDevices.setOnClickListener(v -> selectTab(0));
        navSettings.setOnClickListener(v -> selectTab(1));
    }

    private void selectTab(int t) {
        tab = t;
        boolean main = t == 0;
        scrollMain.setVisibility(main ? View.VISIBLE : View.GONE);
        scrollSettings.setVisibility(main ? View.GONE : View.VISIBLE);
        headerTitle.setText(main ? (cfg.pultUi() ? R.string.title_points : R.string.title_main)
                : R.string.title_settings);
        statusChip.setVisibility(main ? View.VISIBLE : View.GONE);
        btnRefresh.setVisibility(main ? View.VISIBLE : View.INVISIBLE);

        int accent = getColor(R.color.accent);
        int secondary = getColor(R.color.text_secondary);
        navDevicesIcon.setColorFilter(main ? accent : secondary);
        navDevicesText.setTextColor(main ? accent : secondary);
        navSettingsIcon.setColorFilter(main ? secondary : accent);
        navSettingsText.setTextColor(main ? secondary : accent);
        navDevicesText.setText(cfg.pultUi() ? R.string.tab_points : R.string.tab_devices);
        navDevices.setBackgroundResource(main ? R.drawable.bg_nav_pill : 0);
        navSettings.setBackgroundResource(main ? 0 : R.drawable.bg_nav_pill);

        if (cfg.pultUi()) {
            if (main) showPultWeb(); else hidePultWeb();
        } else {
            hidePultWeb();
        }

        if (!main) {
            rebuildSettings();
        } else {
            pollOnce();
        }
    }

    private void reloadDevices() {
        devicesRevision++;
        devices = cfg.getDevices();
        cards.clear();
        lastStatus.clear();
        rebuildMain();
        rebuildSettings();
        updateThemeButtons();
        if (devices.isEmpty()) {
            setHeader(getString(R.string.status_no_devices), R.drawable.dot_muted, getColor(R.color.text_secondary), true);
        } else {
            setHeader(getString(R.string.status_checking), R.drawable.dot_muted, getColor(R.color.text_secondary));
        }
    }

    private void rebuildMain() {
        if (cfg.pultUi()) {
            // Главный экран «Пульт» — локальный WebView с макетом 1:1.
            // Родной список очищаем, чтобы под ним ничего не мигало.
            listMain.removeAllViews();
            cards.clear();
            ensurePultWeb();
            if (pultWebReady) pushPultData();
            return;
        }
        hidePultWeb();
        rebuildClassic();
    }

    /** Локальный WebView с макетом «Пульт». */
    private void ensurePultWeb() {
        if (!cfg.pultUi()) return;
        if (pultWeb != null) {
            if (!pultWebFailed) return;
            ViewGroup parent = (ViewGroup) pultWeb.getParent();
            if (parent != null) parent.removeView(pultWeb);
            pultWeb.destroy();
            pultWeb = null;
            pultWebFailed = false;
            pultWebReady = false;
        }
        ViewGroup content = findViewById(android.R.id.content);
        if (content == null) return;
        final WebView web = new WebView(this);
        pultWeb = web;
        web.setBackgroundColor(getColor(R.color.bg));
        web.setVisibility(View.GONE);
        WebSettings ws = web.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setAllowFileAccessFromFileURLs(true);
        ws.setSupportZoom(false);
        ws.setBuiltInZoomControls(false);
        ws.setDisplayZoomControls(false);
        ws.setJavaScriptCanOpenWindowsAutomatically(false);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        web.addJavascriptInterface(new PultBridge(), "Android");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !request.getUrl().toString().startsWith("file:///android_asset/pult/");
            }

            @Override
            @SuppressWarnings("deprecation")
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return !url.startsWith("file:///android_asset/pult/");
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) runOnUiThread(MainActivity.this::pultFail);
            }
        });
        content.addView(web, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        web.loadUrl("file:///android_asset/pult/index.html");
        ui.postDelayed(() -> {
            if (!pultWebReady && !pultWebFailed && cfg.pultUi() && pultWeb == web) pultFail();
        }, 7000);
    }

    private void showPultWeb() {
        if (pultWeb == null || !pultWebReady || !cfg.pultUi()) return;
        pultWeb.setVisibility(View.VISIBLE);
        applyPultSystemBars();
    }

    private void hidePultWeb() {
        if (pultWeb != null) pultWeb.setVisibility(View.GONE);
    }

    private void applyPultSystemBars() {
        boolean night = isNight();
        int bg = getColor(R.color.bg);
        getWindow().setStatusBarColor(bg);
        getWindow().setNavigationBarColor(bg);
        int flags = getWindow().getDecorView().getSystemUiVisibility();
        if (night) {
            flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            flags &= ~View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        } else {
            flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        }
        getWindow().getDecorView().setSystemUiVisibility(flags);
    }

    private boolean isNight() {
        int mode = getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK;
        return mode == Configuration.UI_MODE_NIGHT_YES;
    }

    private void pultFail() {
        if (pultWebFailed) return;
        pultWebFailed = true;
        pultWebReady = false;
        cfg.setPultUi(false);
        if (pultUi != null) pultUi.setChecked(false);
        if (pultWeb != null) pultWeb.setVisibility(View.GONE);
        toast(getString(R.string.pult_failed));
        rebuildClassic();
        selectTab(0);
    }

    private Device findDevice(String id) {
        if (id == null) return null;
        for (Device d : devices) if (id.equals(d.id)) return d;
        return null;
    }

    private static String kindName(int kind) {
        switch (kind) {
            case Status.READY: return "READY";
            case Status.OPEN: return "OPEN";
            case Status.CLOSED: return "CLOSED";
            case Status.MOVING: return "MOVING";
            case Status.ON: return "ON";
            case Status.OFF: return "OFF";
            case Status.OFFLINE: return "OFFLINE";
            default: return "UNKNOWN";
        }
    }

    private String pultStatus(Device d, Status s) {
        if (!d.isConfigured() && !d.isGate()) return getString(R.string.not_configured_short);
        return s == null ? getString(R.string.status_checking) : s.text;
    }

    private String pultKind(Device d, Status s) {
        if (!d.isConfigured() && !d.isGate()) return "UNKNOWN";
        return s == null ? "UNKNOWN" : kindName(s.kind);
    }

    private boolean pultOnline(Device d, Status s) {
        return (d.isConfigured() || d.isGate()) && s != null
                && s.kind != Status.OFFLINE && s.kind != Status.UNKNOWN;
    }

    private String pultAction(Device d, Status s) {
        if (!d.isConfigured() && !d.isGate()) return getString(R.string.action_setup);
        if (d.isGate()) return getString(R.string.action_open);
        return actionLabel(d, s == null ? new Status(Status.UNKNOWN, "") : s);
    }

    private String pultSourceName(Device d) {
        if (d.isGate()) return "Мост Gate-IP";
        if (Device.SRC_HA.equals(d.source)) return "Home Assistant";
        return Device.protocolLabel(d.protocol);
    }

    private String pultAddress(Device d) {
        if (d.isGate()) return hostOf(cfg.getGateUrl().trim().isEmpty() ? d.address : cfg.getGateUrl());
        if (Device.SRC_HA.equals(d.source)) return hostOf(cfg.getHaUrl());
        return hostOf(d.address);
    }

    private void pushPultData() {
        if (!pultWebReady || pultWeb == null) return;
        try {
            JSONObject root = new JSONObject();
            root.put("theme", isNight() ? "dark" : "light");
            JSONArray arr = new JSONArray();
            for (Device d : devices) {
                Status s = lastStatus.get(d.id);
                JSONObject o = new JSONObject();
                o.put("id", d.id);
                o.put("name", d.name.isEmpty() ? Device.typeLabel(d.type) : d.name);
                o.put("type", d.type);
                o.put("typeLabel", Device.typeLabel(d.type));
                o.put("gate", d.isGate());
                o.put("dirIn", d.dirIn);
                o.put("dirOut", d.dirOut);
                o.put("configured", d.isConfigured() || d.isGate());
                o.put("favorite", d.favorite);
                o.put("hidden", d.homeHidden);
                o.put("sub", sourceLabel(d));
                o.put("sourceName", pultSourceName(d));
                o.put("address", pultAddress(d));
                o.put("status", pultStatus(d, s));
                o.put("kind", pultKind(d, s));
                o.put("action", pultAction(d, s));
                o.put("online", pultOnline(d, s));
                arr.put(o);
            }
            root.put("devices", arr);
            pultWeb.evaluateJavascript("window.pultData(" + root.toString() + ")", null);
        } catch (Exception ignored) {
        }
    }

    private void pushPultState() {
        if (!pultWebReady || pultWeb == null) return;
        try {
            JSONArray arr = new JSONArray();
            for (Device d : devices) {
                Status s = lastStatus.get(d.id);
                JSONObject o = new JSONObject();
                o.put("id", d.id);
                o.put("status", pultStatus(d, s));
                o.put("kind", pultKind(d, s));
                o.put("action", pultAction(d, s));
                o.put("online", pultOnline(d, s));
                arr.put(o);
            }
            JSONObject root = new JSONObject();
            root.put("checking", false);
            root.put("devices", arr);
            pultWeb.evaluateJavascript("window.pultState(" + root.toString() + ")", null);
        } catch (Exception ignored) {
        }
    }

    private final class PultBridge {
        @JavascriptInterface
        public void ready() {
            runOnUiThread(() -> {
                if (!cfg.pultUi()) return;
                pultWebReady = true;
                if (tab == 0) showPultWeb();
                pushPultData();
            });
        }

        @JavascriptInterface
        public void open(String id) {
            runOnUiThread(() -> {
                Device d = findDevice(id);
                if (d != null) onTap(d);
            });
        }

        @JavascriptInterface
        public void openDir(String id, String dir) {
            runOnUiThread(() -> {
                Device d = findDevice(id);
                if (d != null) onTapDir(d, dir);
            });
        }

        @JavascriptInterface
        public void edit(String id) {
            runOnUiThread(() -> {
                if (findDevice(id) != null) openEditor(id);
            });
        }

        @JavascriptInterface
        public void favorite(String id, boolean value) {
            runOnUiThread(() -> {
                Device d = findDevice(id);
                if (d == null) return;
                d.favorite = value;
                cfg.upsert(d);
                toast(getString(value ? R.string.fav_added : R.string.fav_removed));
                pushPultData();
            });
        }

        @JavascriptInterface
        public void hideHome(String id, boolean value) {
            runOnUiThread(() -> {
                Device d = findDevice(id);
                if (d == null) return;
                d.homeHidden = value;
                cfg.upsert(d);
                toast(getString(value ? R.string.home_hidden : R.string.home_shown));
                pushPultData();
            });
        }

        @JavascriptInterface
        public void sheet(boolean open) {
            runOnUiThread(() -> pultSheetOpen = open);
        }

        @JavascriptInterface
        public void reorder(String csv) {
            runOnUiThread(() -> {
                if (csv == null || csv.trim().isEmpty()) return;
                List<Device> current = cfg.getDevices();
                List<Device> next = new ArrayList<>();
                for (String id : csv.split(",")) {
                    for (Device d : current) {
                        if (d.id.equals(id.trim()) && !next.contains(d)) { next.add(d); break; }
                    }
                }
                if (next.isEmpty()) return;
                for (Device d : current) if (!next.contains(d)) next.add(d);
                devices = next;
                cfg.saveDevices(next);
                if (cfg.pultUi()) pushPultData(); else rebuildMain();
            });
        }

        @JavascriptInterface
        public void settings() {
            runOnUiThread(() -> selectTab(1));
        }

        @JavascriptInterface
        public void refresh() {
            runOnUiThread(MainActivity.this::pollOnce);
        }
    }

    /** Классический экран: компактные плитки по две в ряд. Оставлен для отката. */
    private void rebuildClassic() {
        listMain.removeAllViews();
        cards.clear();
        if (devices.isEmpty()) {
            listMain.addView(buildEmptyView());
            return;
        }
        List<Device> favorites = new ArrayList<>();
        List<Device> others = new ArrayList<>();
        for (Device d : devices) {
            if (d.favorite) favorites.add(d); else others.add(d);
        }

        if (favorites.isEmpty()) {
            addTiles(others);
            return;
        }
        listMain.addView(buildSection(getString(R.string.section_favorites)));
        addTiles(favorites);
        if (!others.isEmpty()) {
            listMain.addView(buildAllHeader(allExpanded, others.size()));
            if (allExpanded) addTiles(others);
        }
    }

    /** Новый главный экран: главная точка сверху, остальные — списком. */
    private void rebuildPult() {
        listMain.removeAllViews();
        cards.clear();
        if (devices.isEmpty()) {
            listMain.addView(buildEmptyView());
            return;
        }

        Device hero = null;
        // Главная точка: сначала избранный шлагбаум, потом избранное, потом любой шлагбаум.
        for (Device d : devices) {
            if (!d.isGate() && d.favorite && d.isConfigured()
                    && Device.TYPE_BARRIER.equals(d.type)) { hero = d; break; }
        }
        if (hero == null) {
            for (Device d : devices) {
                if (!d.isGate() && d.favorite && d.isConfigured()) { hero = d; break; }
            }
        }
        if (hero == null) {
            for (Device d : devices) {
                if (!d.isGate() && d.isConfigured() && Device.TYPE_BARRIER.equals(d.type)) {
                    hero = d; break;
                }
            }
        }
        if (hero == null) {
            for (Device d : devices) {
                if (!d.isGate() && d.isConfigured()) { hero = d; break; }
            }
        }

        List<Device> rest = new ArrayList<>();
        for (Device d : devices) if (d != hero) rest.add(d);

        if (hero != null) listMain.addView(buildPultHero(hero).root);

        if (!rest.isEmpty()) {
            listMain.addView(buildSection(getString(hero != null ? R.string.section_more : R.string.section_points)));
            LinearLayout group = new LinearLayout(this);
            group.setOrientation(LinearLayout.VERTICAL);
            group.setBackground(Ui.cardBackground(this));
            LinearLayout.LayoutParams glp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            glp.bottomMargin = dp(10);
            group.setLayoutParams(glp);
            for (int i = 0; i < rest.size(); i++) {
                if (i > 0) {
                    View line = new View(this);
                    line.setBackgroundColor(getColor(R.color.card_stroke));
                    line.setLayoutParams(new LinearLayout.LayoutParams(
                            ViewGroup.LayoutParams.MATCH_PARENT, dp(1)));
                    group.addView(line);
                }
                group.addView(buildPultRow(rest.get(i)).root);
            }
            listMain.addView(group);
        }

        for (List<Card> list : cards.values()) {
            for (Card c : list) {
                Status known = lastStatus.get(c.id);
                if (known != null) applyStatus(c, known);
            }
        }
    }

    private Card buildPultHero(Device d) {
        Card c = new Card();
        c.id = d.id;
        c.device = d;

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(16), dp(16), dp(16));
        root.setBackground(Ui.cardBackground(this));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.bottomMargin = dp(14);
        root.setLayoutParams(lp);

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        root.addView(top);

        ImageView icon = new ImageView(this);
        icon.setLayoutParams(new LinearLayout.LayoutParams(dp(22), dp(22)));
        icon.setImageResource(Device.typeIcon(d.type));
        icon.setColorFilter(getColor(R.color.accent));
        top.addView(icon);

        TextView type = new TextView(this);
        type.setText(Device.typeLabel(d.type).toUpperCase(Locale.getDefault()));
        type.setTextSize(10);
        type.setLetterSpacing(0.12f);
        type.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        type.setTextColor(getColor(R.color.text_muted));
        type.setSingleLine(true);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        tlp.leftMargin = dp(8);
        type.setLayoutParams(tlp);
        top.addView(type);

        TextView status = new TextView(this);
        status.setTextSize(11);
        status.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        status.setSingleLine(true);
        status.setPadding(dp(8), dp(4), dp(8), dp(4));
        status.setBackground(Ui.stroke(getColor(R.color.card), getColor(R.color.card_stroke), dp(999), dp(1)));
        status.setTextColor(getColor(R.color.text_secondary));
        status.setText(R.string.status_checking);
        c.status = status;
        top.addView(status);

        TextView name = new TextView(this);
        name.setText(d.name.isEmpty() ? Device.typeLabel(d.type) : d.name);
        name.setTextSize(20);
        name.setTextColor(getColor(R.color.text_primary));
        name.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        name.setMaxLines(2);
        name.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        nlp.topMargin = dp(10);
        name.setLayoutParams(nlp);
        c.name = name;
        root.addView(name);

        TextView meta = new TextView(this);
        meta.setText(sourceLabel(d));
        meta.setTextSize(12);
        meta.setTextColor(getColor(R.color.text_secondary));
        meta.setSingleLine(true);
        meta.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams mlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        mlp.topMargin = dp(4);
        meta.setLayoutParams(mlp);
        root.addView(meta);

        Button action = new Button(this);
        LinearLayout.LayoutParams alp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(56));
        alp.topMargin = dp(14);
        action.setLayoutParams(alp);
        action.setText(R.string.action_open);
        action.setAllCaps(false);
        action.setTextSize(16);
        action.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        action.setSingleLine(true);
        action.setMinWidth(0);
        action.setMinHeight(0);
        action.setMinimumWidth(0);
        action.setMinimumHeight(0);
        action.setPadding(dp(16), 0, dp(16), 0);
        Ui.styleButton(this, action, R.drawable.btn_tint, R.color.accent, R.drawable.ic_log_in);
        action.setOnClickListener(v -> onTap(d));
        c.action = action;
        root.addView(action);

        root.setOnLongClickListener(v -> {
            openEditor(d.id);
            return true;
        });
        c.root = root;
        registerCard(c);
        return c;
    }

    private Card buildPultRow(Device d) {
        Card c = new Card();
        c.id = d.id;
        c.device = d;

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setMinimumHeight(dp(64));
        row.setPadding(dp(16), dp(12), dp(12), dp(12));
        row.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        ImageView icon = new ImageView(this);
        icon.setLayoutParams(new LinearLayout.LayoutParams(dp(20), dp(20)));
        icon.setImageResource(Device.typeIcon(d.type));
        icon.setColorFilter(getColor(R.color.text_secondary));
        row.addView(icon);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams clp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        clp.leftMargin = dp(12);
        clp.rightMargin = dp(8);
        col.setLayoutParams(clp);

        TextView name = new TextView(this);
        name.setText(d.name.isEmpty() ? Device.typeLabel(d.type) : d.name);
        name.setTextSize(16);
        name.setTextColor(getColor(R.color.text_primary));
        name.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        name.setSingleLine(true);
        name.setEllipsize(TextUtils.TruncateAt.END);
        col.addView(name);

        TextView status = new TextView(this);
        status.setTextSize(12);
        status.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        status.setSingleLine(true);
        status.setEllipsize(TextUtils.TruncateAt.END);
        status.setTextColor(getColor(R.color.text_secondary));
        status.setText(R.string.status_checking);
        LinearLayout.LayoutParams stlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        stlp.topMargin = dp(2);
        status.setLayoutParams(stlp);
        c.status = status;
        col.addView(status);
        row.addView(col);

        if (d.isGate()) {
            ImageView chevron = new ImageView(this);
            chevron.setLayoutParams(new LinearLayout.LayoutParams(dp(16), dp(16)));
            chevron.setImageResource(R.drawable.ic_chevron_right);
            chevron.setColorFilter(getColor(R.color.text_muted));
            row.addView(chevron);
            row.setOnClickListener(v -> showGateActions(d));
        } else {
            Button action = new Button(this);
            LinearLayout.LayoutParams alp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, dp(44));
            action.setLayoutParams(alp);
            action.setText(R.string.action_open);
            action.setAllCaps(false);
            action.setTextSize(12);
            action.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
            action.setSingleLine(true);
            action.setMinWidth(dp(64));
            action.setMinHeight(0);
            action.setMinimumWidth(dp(64));
            action.setMinimumHeight(0);
            action.setPadding(dp(12), 0, dp(12), 0);
            Ui.styleButton(this, action, R.drawable.btn_tint, R.color.accent, R.drawable.ic_log_in);
            action.setOnClickListener(v -> onTap(d));
            c.action = action;
            row.addView(action);
            row.setOnClickListener(v -> onTap(d));
        }

        row.setOnLongClickListener(v -> {
            openEditor(d.id);
            return true;
        });
        c.root = row;
        registerCard(c);
        return c;
    }

    /** У двери Gate-IP направление выбирается в диалоге: у строки нет места на две кнопки. */
    private void showGateActions(Device d) {
        Status s = lastStatus.get(d.id);
        String state = s == null ? getString(R.string.status_checking) : s.text;
        AlertDialog.Builder b = new AlertDialog.Builder(this)
                .setTitle(d.name.isEmpty() ? Device.typeLabel(d.type) : d.name)
                .setMessage(getString(R.string.gate_choose_dir) + "\n" + state);
        if (d.dirIn) b.setPositiveButton(R.string.dir_in, (dialog, which) -> onTapDir(d, "in"));
        if (d.dirOut) b.setNegativeButton(R.string.dir_out, (dialog, which) -> onTapDir(d, "out"));
        b.setNeutralButton(R.string.device_settings, (dialog, which) -> openEditor(d.id));
        if (!d.dirIn && !d.dirOut) {
            b.setPositiveButton(R.string.action_setup, (dialog, which) -> openEditor(d.id));
            b.setNeutralButton(R.string.cancel, null);
        }
        b.show();
    }

    private void registerCard(Card c) {
        List<Card> list = cards.get(c.id);
        if (list == null) {
            list = new ArrayList<>();
            cards.put(c.id, list);
        }
        list.add(c);
    }

    /** Раскладывает устройства компактными плитками по две в ряд. */
    private void addTiles(List<Device> list) {
        int tileWidth = tileWidthPx();
        for (int i = 0; i < list.size(); i += 2) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            rlp.bottomMargin = dp(10);
            row.setLayoutParams(rlp);
            listMain.addView(row);

            int count = Math.min(2, list.size() - i);
            List<Card> built = new ArrayList<>();
            int height = 0;
            for (int j = 0; j < count; j++) {
                Card c = buildCard(list.get(i + j));
                if (!cards.containsKey(c.id)) cards.put(c.id, new ArrayList<>());
                cards.get(c.id).add(c);
                // Высоту берём по содержимому: фиксированная оставляла пустоту снизу.
                c.root.measure(View.MeasureSpec.makeMeasureSpec(tileWidth, View.MeasureSpec.EXACTLY),
                        View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED));
                height = Math.max(height, c.root.getMeasuredHeight());
                built.add(c);
            }
            for (int j = 0; j < count; j++) {
                Card c = built.get(j);
                LinearLayout.LayoutParams clp = new LinearLayout.LayoutParams(0, height, 1f);
                if (j == 0) clp.rightMargin = dp(5); else clp.leftMargin = dp(5);
                c.root.setLayoutParams(clp);
                row.addView(c.root);
                Status known = lastStatus.get(c.id);
                if (known != null) applyStatus(c, known);
            }
            // Нечётное число: пустая плитка, чтобы последняя не растягивалась на весь ряд.
            if (count == 1) {
                View gap = new View(this);
                LinearLayout.LayoutParams glp = new LinearLayout.LayoutParams(0,
                        ViewGroup.LayoutParams.MATCH_PARENT, 1f);
                glp.leftMargin = dp(5);
                gap.setLayoutParams(glp);
                row.addView(gap);
            }
        }
    }

    /** Ширина одной плитки в ряду — нужна, чтобы измерить высоту по содержимому.
     *  Берём чуть меньше настоящей: лучше небольшой запас, чем обрезанный текст. */
    private int tileWidthPx() {
        int screen = getResources().getDisplayMetrics().widthPixels;
        int used = dp(20) * 2 + dp(5) * 2 + dp(8);
        return Math.max(dp(120), (screen - used) / 2);
    }

    private TextView buildSection(String text) {
        TextView title = new TextView(this);
        title.setText(text);
        title.setTextColor(getColor(R.color.text_muted));
        title.setTextSize(10);
        title.setAllCaps(true);
        title.setLetterSpacing(0.14f);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(4);
        lp.bottomMargin = dp(10);
        title.setLayoutParams(lp);
        return title;
    }

    private View buildHint(String text) {
        TextView hint = new TextView(this);
        hint.setText(text);
        hint.setTextColor(getColor(R.color.text_muted));
        hint.setTextSize(12);
        hint.setLineSpacing(dp(2), 1f);
        hint.setPadding(dp(4), dp(4), dp(4), dp(4));
        hint.setLayoutParams(Ui.rowLp(this));
        return hint;
    }

    private View buildAllHeader(boolean expanded, int count) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(16), dp(14), dp(16), dp(14));
        row.setBackground(Ui.cardBackground(this));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(4);
        lp.bottomMargin = dp(10);
        row.setLayoutParams(lp);

        TextView title = new TextView(this);
        title.setText(getString(R.string.section_all_count, count));
        title.setTextColor(getColor(R.color.text_primary));
        title.setTextSize(15);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        title.setLayoutParams(tlp);
        row.addView(title);

        ImageView chevron = new ImageView(this);
        chevron.setLayoutParams(new LinearLayout.LayoutParams(dp(24), dp(24)));
        chevron.setImageResource(R.drawable.ic_chevron_right);
        chevron.setColorFilter(getColor(R.color.text_secondary));
        chevron.setRotation(expanded ? 90f : 0f);
        row.addView(chevron);

        row.setOnClickListener(v -> {
            allExpanded = !allExpanded;
            rebuildMain();
        });
        return row;
    }

    private void toggleFavorite(Device d) {
        d.favorite = !d.favorite;
        cfg.upsert(d);
        toast(getString(d.favorite ? R.string.fav_added : R.string.fav_removed));
        rebuildMain();
    }

    private Card buildCard(Device d) {
        Card c = new Card();
        c.id = d.id;
        c.device = d;

        // Компактная плитка: значок со своим цветом, название в две строки,
        // статус и кнопки действий. В ряд помещается две плитки.
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(10), dp(10), dp(10), dp(10));
        card.setBackground(Ui.cardBackground(this));
        c.root = card;

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        card.addView(top);

        FrameLayout chip = new FrameLayout(this);
        chip.setLayoutParams(new LinearLayout.LayoutParams(dp(28), dp(28)));
        chip.setBackground(Ui.chip(this, getColor(Device.typeColor(d.type)), dp(7)));

        ImageView icon = new ImageView(this);
        icon.setLayoutParams(new FrameLayout.LayoutParams(dp(16), dp(16), Gravity.CENTER));
        icon.setImageResource(Device.typeIcon(d.type));
        icon.setScaleType(ImageView.ScaleType.CENTER_INSIDE);
        icon.setColorFilter(getColor(R.color.on_type));
        c.icon = icon;
        chip.addView(icon);
        top.addView(chip);

        // Состояние показывает огонёк: словами его не дублируем.
        View spacer = new View(this);
        spacer.setLayoutParams(new LinearLayout.LayoutParams(0, 1, 1f));
        top.addView(spacer);

        View dot = new View(this);
        dot.setLayoutParams(new LinearLayout.LayoutParams(dp(11), dp(11)));
        dot.setBackgroundResource(R.drawable.dot_muted);
        c.dot = dot;
        c.status = null;
        c.pill = null;
        top.addView(dot);

        // Имя занимает обе строки и подбирает кегль — длинное название видно целиком.
        TextView name = new TextView(this);
        name.setText(d.name.isEmpty() ? Device.typeLabel(d.type) : d.name);
        name.setTextColor(getColor(R.color.text_primary));
        name.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        name.setMaxLines(2);
        name.setEllipsize(TextUtils.TruncateAt.END);
        name.setAutoSizeTextTypeUniformWithConfiguration(12, 15, 1, TypedValue.COMPLEX_UNIT_SP);
        LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        nlp.topMargin = dp(8);
        name.setLayoutParams(nlp);
        c.name = name;
        card.addView(name);

        TextView source = new TextView(this);
        source.setText(sourceLabel(d));
        source.setTextColor(getColor(R.color.text_secondary));
        source.setTextSize(11);
        source.setSingleLine(true);
        source.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        slp.topMargin = dp(2);
        source.setLayoutParams(slp);
        card.addView(source);

        // У двери с двумя направлениями кнопки стоят друг под другом: «Вход» сверху,
        // «Выход» снизу, одного размера. Так подписи и значки не теснятся в узкой
        // плитке, а разный оттенок подложки подсказывает направление.
        boolean stacked = d.isGate();
        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(stacked ? LinearLayout.VERTICAL : LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams alp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        alp.topMargin = dp(8);
        actions.setLayoutParams(alp);

        if (d.isGate()) {
            // Обе плашки на месте всегда: если направления нет, плашка неактивна,
            // поэтому «Вход» у всех дверей на одной высоте.
            actions.addView(dirButton(d, "in", getString(R.string.dir_in), stacked, d.dirIn));
            actions.addView(dirButton(d, "out", getString(R.string.dir_out), stacked, d.dirOut));
            c.action = null;
            c.stacked = stacked;   // от этого зависит высота плитки в ряду
        } else {
            Button action = new Button(this);
            action.setLayoutParams(new LinearLayout.LayoutParams(0, dp(34), 1f));
            action.setText(R.string.action_open);
            action.setAllCaps(false);
            action.setTextSize(11);
            action.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
            action.setSingleLine(true);
            action.setMinWidth(0);
            action.setMinHeight(0);
            action.setMinimumWidth(0);
            action.setMinimumHeight(0);
            action.setCompoundDrawablePadding(dp(5));
            action.setPadding(dp(6), 0, dp(6), 0);
            action.setEllipsize(TextUtils.TruncateAt.END);
            action.setOnClickListener(v -> onTap(d));
            c.action = action;
            actions.addView(action);
        }
        card.addView(actions);

        // Избранное — в редакторе (долгое нажатие): в компактной плитке места нет.
        card.setOnLongClickListener(v -> {
            openEditor(d.id);
            return true;
        });

        if (!d.isConfigured() && !d.isGate()) {
            if (c.dot != null) c.dot.setContentDescription(getString(R.string.not_configured_short));
            if (c.action != null) {
                c.action.setText(R.string.action_setup);
                Ui.styleButton(this, c.action, R.drawable.btn_secondary, R.color.text_primary,
                        R.drawable.ic_settings);
            }
        }
        return c;
    }

    private void showDeviceMenu(Device d) {
        String[] items = {
                getString(R.string.rename),
                getString(R.string.device_settings),
                getString(d.favorite ? R.string.fav_remove : R.string.fav_add),
        };
        new AlertDialog.Builder(this)
                .setTitle(d.name.isEmpty() ? Device.typeLabel(d.type) : d.name)
                .setItems(items, (dialog, which) -> {
                    if (which == 0) renameDevice(d);
                    else if (which == 1) openEditor(d.id);
                    else toggleFavorite(d);
                })
                .show();
    }

    /** Своё имя: сохраняется в устройстве и не сбрасывается загрузкой дверей. */
    private void renameDevice(Device d) {
        EditText input = new EditText(this);
        input.setText(d.name);
        input.setSelection(input.getText().length());
        input.setSingleLine(true);
        input.setSelectAllOnFocus(true);
        int pad = dp(20);
        FrameLayout box = new FrameLayout(this);
        box.setPadding(pad, dp(8), pad, 0);
        box.addView(input);
        new AlertDialog.Builder(this)
                .setTitle(R.string.rename)
                .setView(box)
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.save, (dialog, which) -> {
                    String name = input.getText().toString().trim();
                    if (name.isEmpty()) {
                        toast(getString(R.string.error_name));
                        return;
                    }
                    d.name = name;
                    d.nameEdited = true;
                    cfg.upsert(d);
                    toast(getString(R.string.saved));
                    reloadDevices();
                })
                .show();
    }

    /** Подпись источника под названием: откуда устройство и чем управляет. */
    private String sourceLabel(Device d) {
        if (d.isGate()) {
            String dirs = d.dirIn && d.dirOut ? "вход и выход"
                    : (d.dirIn ? "только вход" : (d.dirOut ? "только выход" : "нет направлений"));
            return "Gate-IP · " + dirs;
        }
        if (Device.SRC_HA.equals(d.source)) {
            return d.entity.isEmpty() ? "Home Assistant · не выбрана" : "Home Assistant · " + d.entity;
        }
        String base = Device.protocolLabel(d.protocol);
        return d.address.isEmpty() ? base + " · не настроено" : base + " · " + hostOf(d.address);
    }

    private static String hostOf(String address) {
        String value = address == null ? "" : address.trim();
        int scheme = value.indexOf("://");
        if (scheme >= 0) value = value.substring(scheme + 3);
        int slash = value.indexOf('/');
        if (slash >= 0) value = value.substring(0, slash);
        return value;
    }

    private String actionLabel(Device d, Status s) {
        if (!Device.SRC_HA.equals(d.source)) return getString(R.string.action_open);
        switch (domainOf(d.entity)) {
            case "cover":
                if (s.isMoving()) return getString(R.string.action_stop);
                return s.isOpenish() ? getString(R.string.action_close) : getString(R.string.action_open);
            case "lock":
                return s.isOpenish() ? getString(R.string.action_close) : getString(R.string.action_open);
            case "button":
                return getString(R.string.action_press);
            case "script":
                return getString(R.string.action_run);
            default:
                return s.kind == Status.ON ? getString(R.string.action_off) : getString(R.string.action_on);
        }
    }

    private int actionIcon(Device d, Status s) {
        if (s.isMoving()) return R.drawable.ic_square;
        if (!Device.SRC_HA.equals(d.source)) return R.drawable.ic_log_in;
        switch (domainOf(d.entity)) {
            case "cover":
            case "lock":
                return s.isOpenish() ? R.drawable.ic_log_out : R.drawable.ic_log_in;
            case "button":
                return R.drawable.ic_log_in;
            case "script":
            default:
                return R.drawable.ic_power;
        }
    }

    private void applyStatus(Card c, Status s) {
        if (c.status != null) c.status.setText(s.text);
        int color;
        switch (s.kind) {
            case Status.OPEN:
            case Status.ON:
                color = getColor(R.color.success);
                break;
            case Status.MOVING:
                color = getColor(R.color.warn);
                break;
            case Status.READY:
                color = getColor(R.color.accent);
                break;
            case Status.OFFLINE:
                color = getColor(R.color.danger);
                break;
            case Status.CLOSED:
            case Status.OFF:
            case Status.UNKNOWN:
            default:
                color = getColor(R.color.text_secondary);
                break;
        }
        if (c.status != null) c.status.setTextColor(color);
        int dotRes;
        switch (s.kind) {
            case Status.OPEN:
            case Status.ON:
            case Status.READY:
                dotRes = R.drawable.dot_green;
                c.live = true;
                break;
            case Status.MOVING:
                dotRes = R.drawable.dot_amber;
                c.live = true;
                break;
            case Status.OFFLINE:
                dotRes = R.drawable.dot_red;
                c.live = false;
                break;
            default:
                dotRes = R.drawable.dot_muted;
                c.live = false;
                break;
        }
        if (c.dot != null) {
            c.dot.setBackgroundResource(dotRes);
            c.dot.setContentDescription(s.text);
            if (!c.live) c.dot.setAlpha(1f);
        }
        if (c.action == null) return;

        boolean online = s.kind != Status.OFFLINE && s.kind != Status.UNKNOWN;
        c.action.setText(actionLabel(c.device, s));
        int icon = actionIcon(c.device, s);
        if (!online) {
            Ui.styleButton(this, c.action, R.drawable.btn_secondary, R.color.text_muted, icon);
        } else if (s.isMoving()) {
            Ui.styleButton(this, c.action, R.drawable.btn_warn, R.color.warn, icon);
        } else if (s.isOpenish()) {
            Ui.styleButton(this, c.action, R.drawable.btn_secondary, R.color.text_primary, icon);
        } else {
            Ui.styleButton(this, c.action, R.drawable.btn_tint, R.color.accent, icon);
        }
        c.action.setAlpha(online ? 1f : 0.6f);
    }

    private Button dirButton(Device d, String dir, String label, boolean stacked, boolean enabled) {
        boolean out = "out".equals(dir);
        Button b = new Button(this);
        // Обе плашки одного размера: в столбике — во всю ширину, в строке — поровну.
        LinearLayout.LayoutParams lp = stacked
                ? new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(34))
                : new LinearLayout.LayoutParams(0, dp(34), 1f);
        if (stacked && !out) lp.bottomMargin = dp(6);
        b.setLayoutParams(lp);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextSize(11);
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        b.setSingleLine(true);
        b.setMinWidth(0);
        b.setMinHeight(0);
        b.setMinimumWidth(0);
        b.setMinimumHeight(0);
        b.setCompoundDrawablePadding(dp(5));
        b.setPadding(dp(6), 0, dp(6), 0);
        b.setEllipsize(TextUtils.TruncateAt.END);
        if (enabled) {
            // «Вход» с зеленоватой подложкой, «Выход» — с красноватой.
            Ui.styleButton(this, b, out ? R.drawable.btn_out : R.drawable.btn_in,
                    out ? R.color.danger : R.color.accent,
                    out ? R.drawable.ic_log_out : R.drawable.ic_log_in);
            b.setOnClickListener(v -> onTapDir(d, dir));
        } else {
            // Направление у двери не настроено: плашка на месте, но неактивная.
            Ui.styleButton(this, b, R.drawable.btn_secondary, R.color.text_muted,
                    out ? R.drawable.ic_log_out : R.drawable.ic_log_in);
            b.setEnabled(false);
            b.setAlpha(0.55f);
        }
        return b;
    }

    /** Адрес моста: дома — локальный, вне дома — публичный из настроек. */
    private String gateBase(Device d) {
        String publicUrl = cfg.getGateUrl().trim();
        String local = cfg.getGateLocalUrl().trim();
        if (local.isEmpty()) {
            // Старые карточки хранят локальный адрес, которым мост открывался раньше.
            String deviceHost = hostOnly(d.address);
            if (d.isGate() && isPrivateHost(deviceHost)) local = d.address;
        }
        if (!local.isEmpty() && onHomeLan(local)) return HaClient.normalizeBase(local);
        return HaClient.normalizeBase(!publicUrl.isEmpty() ? publicUrl : d.address);
    }

    private static String hostOnly(String address) {
        try {
            String base = HaClient.normalizeBase(address);
            String host = Uri.parse(base).getHost();
            return host == null ? "" : host;
        } catch (Exception e) {
            return "";
        }
    }

    private static boolean isPrivateHost(String host) {
        if (host == null || host.isEmpty()) return false;
        try {
            return InetAddress.getByName(host).isSiteLocalAddress();
        } catch (Exception e) {
            return false;
        }
    }

    /** Телефон в той же подсети, что и локальный адрес моста. */
    private boolean onHomeLan(String url) {
        String host = hostOnly(url);
        if (!isPrivateHost(host)) return false;
        try {
            InetAddress bridge = InetAddress.getByName(host);
            if (!(bridge instanceof Inet4Address)) return false;
            ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            Network active = cm == null ? null : cm.getActiveNetwork();
            LinkProperties lp = active == null ? null : cm.getLinkProperties(active);
            if (lp == null) return false;
            for (LinkAddress la : lp.getLinkAddresses()) {
                InetAddress local = la.getAddress();
                if (local instanceof Inet4Address
                        && sameV4Subnet((Inet4Address) local, (Inet4Address) bridge, la.getPrefixLength())) {
                    return true;
                }
            }
        } catch (Exception ignored) {}
        return false;
    }

    private static boolean sameV4Subnet(Inet4Address a, Inet4Address b, int prefixLength) {
        int bits = Math.max(0, Math.min(32, prefixLength));
        int mask = bits == 0 ? 0 : (0xFFFFFFFF << (32 - bits));
        return (v4ToInt(a) & mask) == (v4ToInt(b) & mask);
    }

    private static int v4ToInt(Inet4Address address) {
        byte[] b = address.getAddress();
        return ((b[0] & 0xFF) << 24) | ((b[1] & 0xFF) << 16)
                | ((b[2] & 0xFF) << 8) | (b[3] & 0xFF);
    }

    private void onTapDir(Device d, String dir) {
        final String base = gateBase(d);
        if (base.isEmpty()) { toast("Укажите адрес моста"); return; }
        final String token = cfg.getGateToken();
        if (token.isEmpty()) { askGateKey(null); return; }
        runCommand(() -> {
            Http.Response r = Http.getGate(base + "/open?id=" + Uri.encode(d.gateId) + "&dir=" + dir
                    + "&token=" + Uri.encode(token));
            if (authFailed(r)) {
                ui.post(() -> askGateKey(getString(R.string.gate_key_bad)));
                return getString(R.string.gate_key_bad);
            }
            String error = GateResponse.commandError(r);
            return error == null ? getString(R.string.cmd_sent) : error;
        });
    }

    private void onTap(Device d) {
        if (!d.isConfigured()) {
            openEditor(d.id);
            return;
        }
        if (Device.SRC_HA.equals(d.source) && !cfg.hasHa()) {
            toast(getString(R.string.status_ha_not_set));
            selectTab(1);
            return;
        }
        if (Device.SRC_HA.equals(d.source)) {
            final String domain = domainOf(d.entity);
            final Status status = lastStatus.get(d.id);
            if (("cover".equals(domain) || "lock".equals(domain)) &&
                    (status == null || status.kind == Status.UNKNOWN || status.kind == Status.OFFLINE ||
                     ("lock".equals(domain) && status.isMoving()))) {
                toast("Состояние неизвестно. Обновите связь перед управлением");
                pollOnce();
                return;
            }
            final String service = serviceFor(domain, status);
            final String url = cfg.getHaUrl(), token = cfg.getHaToken();
            final boolean insecure = cfg.haInsecure();
            runCommand(() -> {
                HaClient.Result<String> r = new HaClient(url, token, insecure)
                        .callService(domain, service, d.entity);
                return r.error == null ? getString(R.string.cmd_sent) : "Нет подтверждения команды: " + r.error;
            });
        } else {
            final boolean insecure = cfg.haInsecure();
            runCommand(() -> {
                DirectClient.Result r = DirectClient.toggle(d, insecure);
                return r.error == null ? getString(R.string.cmd_sent) : r.error;
            });
        }
    }

    // Команды не стоят в очереди за опросом или скачиванием и не накапливаются.
    private void runCommand(java.util.concurrent.Callable<String> work) {
        if (commands == null || commands.isShutdown()) return;
        if (!commandInFlight.compareAndSet(false, true)) {
            toast("Дождитесь завершения предыдущей команды");
            return;
        }
        // Отбросить старый опрос: после действия состояние может измениться.
        devicesRevision++;
        lastStatus.clear();
        try {
            commands.execute(() -> {
                String message;
                try { message = work.call(); }
                catch (Exception e) { message = "Результат команды неизвестен"; }
                final String result = message;
                commandInFlight.set(false);
                ui.post(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    toast(result);
                    pollOnce();
                });
            });
        } catch (Exception e) {
            commandInFlight.set(false);
            toast("Не удалось отправить команду");
        }
    }

    private String serviceFor(String domain, Status st) {
        switch (domain) {
            case "cover":
                if (st != null && st.isMoving()) return "stop_cover";
                if (st != null && st.isOpenish()) return "close_cover";
                return "open_cover";
            case "lock":
                if (st != null && st.isOpenish()) return "lock";
                return "unlock";
            case "button":
                return "press";
            case "script":
                return "turn_on";
            default:
                return "toggle";
        }
    }

    private static String domainOf(String entity) {
        if (entity == null) return "";
        int i = entity.indexOf('.');
        return i > 0 ? entity.substring(0, i) : "";
    }

    private Status statusFromHa(HaClient.State s) {
        String domain = domainOf(s.id);
        String state = s.state == null ? "" : s.state.toLowerCase(Locale.ROOT);
        if ("unavailable".equals(state)) return new Status(Status.OFFLINE, "Недоступно");
        if ("unknown".equals(state)) return new Status(Status.UNKNOWN, "Неизвестно");
        switch (domain) {
            case "cover":
                if ("open".equals(state)) return new Status(Status.OPEN, "Открыто");
                if ("closed".equals(state)) return new Status(Status.CLOSED, "Закрыто");
                if ("opening".equals(state)) return new Status(Status.MOVING, "Открывается…");
                if ("closing".equals(state)) return new Status(Status.MOVING, "Закрывается…");
                return new Status(Status.UNKNOWN, state.isEmpty() ? "Нет данных" : state);
            case "lock":
                if ("locked".equals(state)) return new Status(Status.CLOSED, "Закрыто");
                if ("unlocked".equals(state)) return new Status(Status.OPEN, "Открыто");
                if ("locking".equals(state)) return new Status(Status.MOVING, "Закрывается…");
                if ("unlocking".equals(state)) return new Status(Status.MOVING, "Открывается…");
                return new Status(Status.UNKNOWN, state.isEmpty() ? "Нет данных" : state);
            case "button":
                return new Status(Status.READY, "Кнопка");
            case "script":
                if ("on".equals(state)) return new Status(Status.ON, "Выполняется");
                return new Status(Status.OFF, "Готов");
            default:
                if ("on".equals(state)) return new Status(Status.ON, "Включено");
                if ("off".equals(state)) return new Status(Status.OFF, "Выключено");
                return new Status(Status.UNKNOWN, state.isEmpty() ? "Нет данных" : state);
        }
    }

    private void importGateDoors() {
        importGate(false);
    }

    private boolean hasGateDevices() {
        for (Device d : cfg.getDevices()) {
            if (d.isGate()) return true;
        }
        return false;
    }

    private void autoImportGate() {
        if (importingGate || hasGateDevices()) return;
        if (cfg.getGateUrl().trim().isEmpty()) return;
        importGate(true);
    }

    private void importGate(final boolean silent) {
        if (importingGate) return;
        importingGate = true;
        final String rawUrl = gateUrl.getText().toString().trim();
        final String token = gateToken.getText().toString().trim();
        cfg.setGateUrl(rawUrl);
        if (token.isEmpty()) {
            // Без ключа мост ответит отказом — спрашиваем его сразу.
            importingGate = false;
            askGateKey(null);
            return;
        }
        cfg.setGateToken(token);
        final String base = HaClient.normalizeBase(rawUrl);
        if (base.isEmpty()) {
            importingGate = false;
            if (!silent) {
                gateStatus.setTextColor(getColor(R.color.danger));
                gateStatus.setText(getString(R.string.gate_error, "укажите адрес моста"));
            }
            return;
        }
        btnGateImport.setEnabled(false);
        if (!silent) {
            gateStatus.setTextColor(getColor(R.color.text_muted));
            gateStatus.setText(R.string.gate_loading);
        }
        final String encToken = Uri.encode(token);
        runIo(() -> {
            Http.Response r = Http.get(base + "/doors?token=" + encToken, null, false);
            ui.post(() -> {
                if (isFinishing() || isDestroyed()) return;
                importingGate = false;
                btnGateImport.setEnabled(true);
                String error = null;
                int added = 0;
                if (!rawUrl.equals(cfg.getGateUrl()) || !token.equals(cfg.getGateToken())) {
                    error = "настройки моста изменились, повторите загрузку";
                } else if (authFailed(r)) {
                    error = "ключ не принят";
                    gateKeyPromptShown = false;
                    askGateKey(getString(R.string.gate_key_bad));
                } else if (!r.ok()) {
                    error = r.error == null ? "HTTP " + r.code : r.error;
                } else {
                  try {
                    JSONArray arr = new JSONObject(r.body).getJSONArray("doors");
                    List<Device> devices = cfg.getDevices();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject o = arr.getJSONObject(i);
                        String id = o.optString("id", "");
                        String name = o.optString("name", "");
                        if (id.isEmpty() || name.isEmpty()) continue;
                        JSONArray readers = o.optJSONArray("readers");
                        boolean in = false, out = false;
                        if (readers != null) {
                            for (int k = 0; k < readers.length(); k++) {
                                String dir = readers.getJSONObject(k).optString("dir", "in");
                                if ("out".equals(dir)) out = true; else in = true;
                            }
                        }
                        Device found = null;
                        for (Device d : devices) {
                            if (id.equals(d.gateId)) { found = d; break; }
                        }
                        if (found == null) {
                            found = new Device(Device.newId(), name, Device.TYPE_WIDE);
                            devices.add(found);
                        }
                        if (!found.nameEdited) found.name = name;
                        found.source = Device.SRC_HTTP;
                        found.protocol = Device.P_CUSTOM;
                        found.address = base;
                        found.gateId = id;
                        found.gateToken = token;
                        found.dirIn = in;
                        found.dirOut = out;
                        found.pulse = false;
                        found.openUrl = "";
                        found.closeUrl = "";
                        found.statusUrl = "";
                        found.statusField = "";
                        added++;
                    }
                    cfg.saveDevices(devices);
                  } catch (Exception e) {
                    error = "некорректный ответ моста";
                  }
                }
                if (error != null) {
                    gateStatus.setTextColor(getColor(R.color.danger));
                    gateStatus.setText(getString(R.string.gate_error, error));
                    if (silent && tab == 0) {
                        setHeader(getString(R.string.gate_unreachable, error),
                                R.drawable.dot_red, getColor(R.color.danger), true);
                    }
                } else {
                    gateStatus.setTextColor(getColor(R.color.accent));
                    gateStatus.setText(getString(R.string.gate_ok, added));
                    reloadDevices();
                }
            });
        });
    }

    private void testConnection() {
        final String url = haUrl.getText().toString().trim();
        final String token = haToken.getText().toString().trim();
        cfg.setHaUrl(url);
        cfg.setHaToken(token);
        if (url.isEmpty()) {
            testResult.setTextColor(getColor(R.color.danger));
            testResult.setText("Укажите адрес Home Assistant");
            return;
        }
        if (token.isEmpty()) {
            testResult.setTextColor(getColor(R.color.danger));
            testResult.setText("Укажите долгоживущий токен");
            return;
        }
        btnTest.setEnabled(false);
        testResult.setTextColor(getColor(R.color.text_secondary));
        testResult.setText(R.string.status_checking);
        final boolean insecure = haInsecure.isChecked();
        runIo(() -> {
            HaClient.Result<List<HaClient.State>> r = new HaClient(url, token, insecure).states();
            ui.post(() -> {
                btnTest.setEnabled(true);
                if (r.error == null) {
                    testResult.setTextColor(getColor(R.color.accent));
                    testResult.setText(getString(R.string.ha_ok, r.value.size()));
                    pollOnce();
                } else {
                    testResult.setTextColor(getColor(R.color.danger));
                    testResult.setText(r.error);
                }
            });
        });
    }

    private Button themeLight, themeDark, themeSystem;

    private void applyTheme(int mode) {
        cfg.setThemeMode(mode);
        updateThemeButtons();
        recreate();
    }

    private void updateThemeButtons() {
        if (themeLight == null) return;
        int mode = cfg.getThemeMode();
        styleThemeButton(themeLight, mode == 1);
        styleThemeButton(themeDark, mode == 2);
        styleThemeButton(themeSystem, mode == 0);
    }

    private void styleThemeButton(Button b, boolean active) {
        b.setBackgroundResource(active ? R.drawable.btn_primary : R.drawable.btn_secondary);
        b.setTextColor(getColor(active ? R.color.on_accent : R.color.text_primary));
    }

    private void rebuildSettings() {
        deviceSettings.removeAllViews();
        if (devices.isEmpty()) {
            TextView empty = new TextView(this);
            empty.setText("Устройств пока нет — добавьте ниже");
            empty.setTextColor(getColor(R.color.text_muted));
            empty.setTextSize(13);
            empty.setPadding(dp(4), dp(8), dp(4), dp(8));
            deviceSettings.addView(empty);
            return;
        }
        for (Device d : devices) {
            deviceSettings.addView(buildSettingsRow(d));
        }
    }

    private View buildSettingsRow(Device d) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(12), dp(8), dp(12));
        row.setBackground(Ui.cardBackground(this));
        row.setLayoutParams(Ui.rowLp(this));

        ImageView icon = new ImageView(this);
        LinearLayout.LayoutParams ilp = new LinearLayout.LayoutParams(dp(32), dp(32));
        icon.setLayoutParams(ilp);
        icon.setImageResource(Device.typeIcon(d.type));
        icon.setColorFilter(getColor(R.color.accent_deep));
        row.addView(icon);

        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams clp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        clp.leftMargin = dp(12);
        clp.rightMargin = dp(6);
        col.setLayoutParams(clp);

        TextView name = new TextView(this);
        name.setText(d.name.isEmpty() ? Device.typeLabel(d.type) : d.name);
        name.setTextColor(getColor(R.color.text_primary));
        name.setTextSize(15);
        name.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        name.setSingleLine(false);
        name.setMaxLines(2);
        name.setEllipsize(TextUtils.TruncateAt.END);
        col.addView(name);

        String typeName = Device.typeLabel(d.type);
        if (d.name != null && (d.name.equals("Ворота") || d.name.equals("Калитка") || d.name.equals("Шлагбаум")))
            typeName = "";
        TextView sub = new TextView(this);
        sub.setText(typeName.isEmpty() ? sourceText(d) : (typeName + " · " + sourceText(d)));
        sub.setTextColor(getColor(R.color.text_muted));
        sub.setTextSize(12);
        sub.setSingleLine(true);
        sub.setEllipsize(TextUtils.TruncateAt.END);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        slp.topMargin = dp(3);
        sub.setLayoutParams(slp);
        col.addView(sub);
        row.addView(col);

        ImageButton del = new ImageButton(this);
        del.setLayoutParams(new LinearLayout.LayoutParams(dp(40), dp(40)));
        del.setPadding(dp(9), dp(9), dp(9), dp(9));
        del.setBackgroundResource(R.drawable.bg_circle_ripple);
        del.setImageResource(R.drawable.ic_trash_2);
        del.setColorFilter(getColor(R.color.text_muted));
        del.setContentDescription(getString(R.string.delete));
        del.setOnClickListener(v -> confirmDelete(d));
        row.addView(del);

        row.setOnClickListener(v -> openEditor(d.id));
        return row;
    }

    private String sourceText(Device d) {
        if (Device.SRC_HA.equals(d.source)) {
            return d.entity.isEmpty() ? "Home Assistant · не выбрана" : "Home Assistant · " + d.entity;
        }
        String base = Device.protocolLabel(d.protocol);
        return d.address.isEmpty() ? base + " · не настроено" : base + " · " + d.address;
    }

    private void confirmDelete(Device d) {
        new AlertDialog.Builder(this)
                .setTitle(R.string.delete_title)
                .setMessage(getString(R.string.delete_text, d.name.isEmpty() ? Device.typeLabel(d.type) : d.name))
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.delete, (dialog, which) -> {
                    cfg.delete(d.id);
                    reloadDevices();
                })
                .show();
    }

    private View buildEmptyView() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER_HORIZONTAL);
        box.setPadding(0, dp(56), 0, dp(24));
        box.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        FrameLayout circle = new FrameLayout(this);
        LinearLayout.LayoutParams clp = new LinearLayout.LayoutParams(dp(96), dp(96));
        circle.setLayoutParams(clp);
        circle.setBackground(Ui.fill(getColor(R.color.accent_soft), dp(999)));
        ImageView icon = new ImageView(this);
        icon.setLayoutParams(new FrameLayout.LayoutParams(dp(44), dp(44), Gravity.CENTER));
        icon.setImageResource(R.drawable.ic_door_open);
        icon.setColorFilter(getColor(R.color.accent));
        circle.addView(icon);
        box.addView(circle);

        TextView title = new TextView(this);
        title.setText(R.string.empty_title);
        title.setTextColor(getColor(R.color.text_primary));
        title.setTextSize(18);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tlp.topMargin = dp(18);
        title.setLayoutParams(tlp);
        box.addView(title);

        TextView sub = new TextView(this);
        sub.setText(R.string.empty_subtitle);
        sub.setTextColor(getColor(R.color.text_muted));
        sub.setTextSize(13);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        slp.topMargin = dp(6);
        sub.setLayoutParams(slp);
        box.addView(sub);

        Button add = new Button(this);
        add.setText(R.string.empty_button);
        add.setAllCaps(false);
        add.setTextSize(14);
        add.setTextColor(getColor(R.color.on_accent));
        add.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        add.setBackgroundResource(R.drawable.btn_primary);
        add.setPadding(dp(22), dp(14), dp(22), dp(14));
        add.setMinHeight(dp(48));
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        blp.topMargin = dp(20);
        add.setLayoutParams(blp);
        add.setOnClickListener(v -> selectTab(1));
        box.addView(add);
        return box;
    }

    private void updateHeader(boolean hasHa, boolean failed, boolean gateFailed) {
        int gate = 0, ha = 0, direct = 0;
        for (Device d : devices) {
            if (d.isGate()) gate++;
            else if (Device.SRC_HA.equals(d.source) && d.isConfigured()) ha++;
            else if (d.isConfigured()) direct++;
        }
        if (gate == 0 && ha == 0 && direct == 0) {
            setHeader("Настройте устройства", R.drawable.dot_muted, getColor(R.color.text_secondary), true);
            return;
        }
        if (ha > 0 && !cfg.hasHa()) {
            setHeader(getString(R.string.status_ha_not_set), R.drawable.dot_amber, getColor(R.color.warn), true);
            return;
        }
        if (ha > 0 && gate > 0) {
            boolean anyFailed = failed || gateFailed;
            setHeader(anyFailed ? "Проблема связи с HA или мостом" : "HA и мост доступны",
                    anyFailed ? R.drawable.dot_red : R.drawable.dot_green,
                    getColor(anyFailed ? R.color.danger : R.color.accent));
            return;
        }
        if (ha > 0) {
            setHeader(failed ? getString(R.string.status_ha_offline) : getString(R.string.status_ha_online),
                    failed ? R.drawable.dot_red : R.drawable.dot_green,
                    failed ? getColor(R.color.danger) : getColor(R.color.accent));
            return;
        }
        if (gate > 0) {
            String text = gateFailed ? "Мост СКУД · нет связи" : "Мост СКУД доступен";
            setHeader(text, gateFailed ? R.drawable.dot_red : R.drawable.dot_green,
                    gateFailed ? getColor(R.color.danger) : getColor(R.color.accent));
            return;
        }
        setHeader(getString(R.string.status_direct), R.drawable.dot_blue, getColor(R.color.info));
    }

    private String doorsWord(int n) {
        int m10 = n % 10, m100 = n % 100;
        if (m10 == 1 && m100 != 11) return "дверь";
        if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "двери";
        return "дверей";
    }

    private void setHeader(String text, int dotRes, int color) {
        setHeader(text, dotRes, color, false);
    }

    /** showText — только для подсказок вроде «Добавьте устройство»:
     *  состояние связи показывает пульсирующий огонёк, без подписи. */
    private void setHeader(String text, int dotRes, int color, boolean showText) {
        statusText.setText(showText ? text : "");
        statusText.setVisibility(showText ? View.VISIBLE : View.GONE);
        statusText.setTextColor(color);
        statusDot.setBackgroundResource(dotRes);
        statusDot.setContentDescription(text);
    }

    private void pollOnce() {
        if (io == null || io.isShutdown() || commandInFlight.get()) return;
        if (!inFlight.compareAndSet(false, true)) return;
        final List<Device> snapshot = new ArrayList<>(devices);
        final int revision = devicesRevision;
        final String haUrl = cfg.getHaUrl().trim();
        final String haToken = cfg.getHaToken().trim();
        final String gateToken = cfg.getGateToken();
        final boolean insecure = cfg.haInsecure();
        try {
            io.execute(() -> {
                final Map<String, Status> results = new HashMap<>();
                final List<Device> haDevices = new ArrayList<>();
                for (Device d : snapshot) {
                    if (Device.SRC_HA.equals(d.source)) haDevices.add(d);
                }
                final boolean hasHa = !haDevices.isEmpty();
                boolean failed = false;
                if (hasHa) {
                    if (haUrl.isEmpty() || haToken.isEmpty()) {
                        failed = true;
                        for (Device d : haDevices) results.put(d.id, new Status(Status.OFFLINE, "Не настроено"));
                    } else {
                        HaClient.Result<List<HaClient.State>> r =
                                new HaClient(haUrl, haToken, insecure).states();
                        if (r.error != null) {
                            failed = true;
                            for (Device d : haDevices) results.put(d.id, new Status(Status.OFFLINE, "Нет связи"));
                        } else {
                            Map<String, HaClient.State> byId = new HashMap<>();
                            for (HaClient.State s : r.value) byId.put(s.id, s);
                            for (Device d : haDevices) {
                                HaClient.State s = byId.get(d.entity);
                                results.put(d.id, s == null
                                        ? new Status(Status.UNKNOWN, "Не найдено")
                                        : statusFromHa(s));
                            }
                        }
                    }
                }
                boolean gateFailed = false, gateAuth = false, gateKeyMissing = false;
                Map<String, Boolean> gateBases = new HashMap<>();
                Map<String, Boolean> gateAuthBases = new HashMap<>();
                Map<String, Boolean> gateCalibrated = new HashMap<>();
                for (Device d : snapshot) {
                    if (!d.isGate()) continue;
                    String base = gateBase(d);
                    if (base.isEmpty()) { results.put(d.id, new Status(Status.UNKNOWN, "Не настроено")); continue; }
                    if (gateToken.isEmpty()) {
                        // Ключ ещё не введён: мост ответит отказом, поэтому спрашиваем один раз.
                        gateKeyMissing = true;
                        results.put(d.id, new Status(Status.OFFLINE, getString(R.string.gate_key_needed)));
                        continue;
                    }
                    String cacheKey = base + "\n" + gateToken;
                    Boolean ok = gateBases.get(cacheKey);
                    boolean auth = Boolean.TRUE.equals(gateAuthBases.get(cacheKey));
                    if (ok == null) {
                        Http.Response r = Http.get(base + "/status?token=" + Uri.encode(gateToken), null, false);
                        ok = r.ok();
                        auth = !ok && authFailed(r);
                        boolean calibrated = true;
                        if (ok) {
                            try {
                                JSONObject body = new JSONObject(r.body);
                                calibrated = body.optBoolean("calibrated", true);
                            } catch (Exception ignored) {}
                        }
                        gateBases.put(cacheKey, ok);
                        gateAuthBases.put(cacheKey, auth);
                        gateCalibrated.put(cacheKey, calibrated);
                        if (auth) gateAuth = true;
                    }
                    if (ok) {
                        boolean calibrated = !Boolean.FALSE.equals(gateCalibrated.get(cacheKey));
                        results.put(d.id, calibrated
                                ? new Status(Status.READY, "Доступен")
                                : new Status(Status.MOVING, "Не откалиброван"));
                    } else {
                        gateFailed = true;
                        results.put(d.id, new Status(Status.OFFLINE,
                                auth ? getString(R.string.gate_key_bad_short) : "Нет связи"));
                    }
                }
                for (Device d : snapshot) {
                    if (Device.SRC_HA.equals(d.source)) continue;
                    if (d.isGate()) continue;
                    if (!d.isConfigured()) {
                        results.put(d.id, new Status(Status.UNKNOWN, "Не настроено"));
                    } else if (d.pulse && !Device.P_CUSTOM.equals(d.protocol)) {
                        results.put(d.id, new Status(Status.READY, "Готов"));
                    } else {
                        results.put(d.id, DirectClient.status(d, insecure));
                    }
                }
                final boolean fFailed = failed;
                final boolean fGateFailed = gateFailed;
                final boolean fGateAuth = gateAuth;
                final boolean fGateKeyMissing = gateKeyMissing;
                ui.post(() -> {
                    inFlight.set(false);
                    if (revision != devicesRevision) {
                        pollOnce();
                        return;
                    }
                    lastStatus.putAll(results);
                    for (Map.Entry<String, List<Card>> entry : cards.entrySet()) {
                        Status s = results.get(entry.getKey());
                        if (s == null) continue;
                        for (Card c : entry.getValue()) {
                            if (c.device.isConfigured()) applyStatus(c, s);
                        }
                    }
                    updateHeader(hasHa, fFailed, fGateFailed);
                    pushPultState();
                    if (fGateAuth) askGateKey(getString(R.string.gate_key_bad));
                    else if (fGateKeyMissing) askGateKey(null);
                });
            });
        } catch (Exception e) {
            inFlight.set(false);
        }
    }

    private final Runnable pollTask = new Runnable() {
        @Override
        public void run() {
            if (!polling) return;
            pollOnce();
            ui.postDelayed(this, 5000);
        }
    };

    /** Огонёк в шапке дышит: видно, что приложение живо и следит за связью. */
    private void startPulse() {
        if (statusDot == null || pulse != null) return;
        pulse = ObjectAnimator.ofPropertyValuesHolder(statusDot, pulseFrames());
        pulse.setDuration(PULSE_PERIOD);
        pulse.setRepeatCount(ValueAnimator.INFINITE);
        pulse.start();
    }

    /** Один такт: короткая волна и длинная пауза — дышит редко и не ярко. */
    private static PropertyValuesHolder pulseFrames() {
        return PropertyValuesHolder.ofKeyframe("alpha",
                Keyframe.ofFloat(0f, 0.55f),
                Keyframe.ofFloat(0.15f, 0.85f),
                Keyframe.ofFloat(0.32f, 0.55f),
                Keyframe.ofFloat(1f, 0.55f));
    }

    private void stopPulse() {
        if (pulse == null) return;
        pulse.cancel();
        pulse = null;
        if (statusDot != null) statusDot.setAlpha(1f);
    }

    /** Огоньки на плитках дышат — видно, что устройство на связи. */
    private void startCardPulse() {
        if (cardPulse != null) return;
        cardPulse = ValueAnimator.ofPropertyValuesHolder(pulseFrames());
        cardPulse.setDuration(PULSE_PERIOD);
        cardPulse.setRepeatCount(ValueAnimator.INFINITE);
        cardPulse.addUpdateListener(animation -> {
            float value = (float) animation.getAnimatedValue("alpha");
            for (List<Card> list : cards.values()) {
                for (Card card : list) {
                    if (card.live && card.dot != null) card.dot.setAlpha(value);
                }
            }
        });
        cardPulse.start();
    }

    private void stopCardPulse() {
        if (cardPulse == null) return;
        cardPulse.cancel();
        cardPulse = null;
    }

    private void startPolling() {
        if (polling) return;
        polling = true;
        ui.postDelayed(pollTask, 250);
    }

    private void stopPolling() {
        polling = false;
        ui.removeCallbacks(pollTask);
    }

    @Override
    protected void onResume() {
        super.onResume();
        reloadDevices();
        startPulse();
        startCardPulse();
        startPolling();
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopPolling();
        stopPulse();
        stopCardPulse();
    }

    @Override
    public void onBackPressed() {
        // Жест «назад» сначала сворачивает открытую карточку/скрытые точки.
        if (cfg.pultUi() && pultWeb != null && pultWebReady && pultSheetOpen) {
            pultSheetOpen = false;
            pultWeb.evaluateJavascript("window.pultBack && window.pultBack()", null);
            return;
        }
        if (tab == 1) {
            selectTab(0);
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (pultWeb != null) {
            ViewGroup parent = (ViewGroup) pultWeb.getParent();
            if (parent != null) parent.removeView(pultWeb);
            pultWeb.destroy();
            pultWeb = null;
        }
        stopPolling();
        stopPulse();
        stopCardPulse();
        ui.removeCallbacksAndMessages(null);
        if (io != null) io.shutdownNow();
        if (commands != null && !commands.shutdownNow().isEmpty()) commandInFlight.set(false);
        super.onDestroy();
    }

    private String appVersion() {
        try {
            PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            return info.versionName == null ? "1.0" : info.versionName;
        } catch (Exception e) {
            return "1.0";
        }
    }

    private void checkUpdates(final boolean silent) {
        if (checkingUpdates) return;
        checkingUpdates = true;
        btnCheckUpdates.setEnabled(false);
        if (!silent) {
            updateStatus.setTextColor(getColor(R.color.text_muted));
            updateStatus.setText(R.string.update_checking);
        }
        final String version = appVersion();
        runIo(() -> {
            final UpdateChecker.Info info = UpdateChecker.check(version);
            ui.post(() -> {
                if (isFinishing() || isDestroyed()) return;
                checkingUpdates = false;
                btnCheckUpdates.setEnabled(true);
                if (info.error != null) {
                    updateStatus.setTextColor(getColor(R.color.text_muted));
                    updateStatus.setText(silent ? getString(R.string.update_offline)
                            : getString(R.string.update_error, info.error));
                    return;
                }
                if (info.newer) {
                    pendingApkUrl = info.apkUrl;
                    updateStatus.setTextColor(getColor(R.color.accent));
                    updateStatus.setText(getString(R.string.update_available, info.tag));
                    btnInstallUpdate.setVisibility(View.VISIBLE);
                    if (silent && !info.tag.equals(cfg.getPromptedUpdate())) {
                        cfg.setPromptedUpdate(info.tag);
                        showUpdateDialog(info);
                    }
                } else {
                    pendingApkUrl = null;
                    btnInstallUpdate.setVisibility(View.GONE);
                    updateStatus.setTextColor(getColor(R.color.text_secondary));
                    updateStatus.setText(R.string.update_none);
                }
            });
        });
    }

    private void showUpdateDialog(final UpdateChecker.Info info) {
        if (isFinishing() || isDestroyed()) return;
        String notes = info.notes == null ? "" : info.notes.trim();
        if (notes.length() > 600) notes = notes.substring(0, 600) + "…";
        if (notes.isEmpty()) notes = getString(R.string.update_available, info.tag);
        new AlertDialog.Builder(this)
                .setTitle(getString(R.string.update_dialog_title) + " " + info.tag)
                .setMessage(notes)
                .setNegativeButton(R.string.update_later, null)
                .setPositiveButton(R.string.update_now, (dialog, which) -> downloadAndInstall(info.apkUrl))
                .show();
    }

    private void downloadAndInstall(final String url) {
        if (downloadingUpdate || isFinishing() || isDestroyed()) return;
        downloadingUpdate = true;
        final ProgressDialog progress = ProgressDialog.show(this, "",
                getString(R.string.update_downloading), true, false);
        runIo(() -> {
            File apk = new File(UpdateProvider.updateDir(MainActivity.this), "Vorota-update.apk");
            final String error = UpdateChecker.download(url, apk);
            ui.post(() -> {
                downloadingUpdate = false;
                try { progress.dismiss(); } catch (Exception ignored) {}
                if (isFinishing() || isDestroyed()) return;
                if (error != null) {
                    updateStatus.setTextColor(getColor(R.color.danger));
                    updateStatus.setText(getString(R.string.update_error, error));
                    return;
                }
                installApk(apk);
            });
        });
    }

    private void installApk(File apk) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(UpdateProvider.uriFor(apk), "application/vnd.android.package-archive");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            startActivity(intent);
        } catch (Exception e) {
            toast(getString(R.string.update_no_installer));
        }
    }

    private void openEditor(String id) {
        Intent intent = new Intent(this, DeviceEditActivity.class);
        if (id != null) intent.putExtra("device_id", id);
        startActivity(intent);
    }

    /** Ключ доступа спрашиваем один раз: дальше он лежит в приватных prefs. */
    private void askGateKeyIfNeeded() {
        if (!cfg.hasGateToken()) askGateKey(null);
    }

    private void askGateKey(String reason) {
        if (isFinishing() || isDestroyed() || gateKeyPromptShown) return;
        gateKeyPromptShown = true;

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(20);
        box.setPadding(pad, dp(6), pad, dp(4));

        TextView hint = new TextView(this);
        hint.setText(reason == null || reason.isEmpty()
                ? getString(R.string.gate_key_hint)
                : reason);
        hint.setTextSize(14);
        hint.setTextColor(getColor(R.color.text_muted));
        box.addView(hint);

        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setText(cfg.getGateToken());
        input.setHint(R.string.gate_key_placeholder);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        input.setTextSize(15);
        input.setTextColor(getColor(R.color.text_primary));
        input.setHintTextColor(getColor(R.color.text_muted));
        input.setBackgroundResource(R.drawable.bg_field);
        int ip = dp(14);
        input.setPadding(ip, dp(10), ip, dp(10));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(12);
        box.addView(input, lp);

        new AlertDialog.Builder(this)
                .setTitle(R.string.gate_key_title)
                .setView(box)
                .setPositiveButton(R.string.gate_key_save, (dialog, which) -> {
                    String key = input.getText().toString().trim();
                    if (key.isEmpty()) {
                        toast(getString(R.string.gate_key_empty));
                        gateKeyPromptShown = false;
                        askGateKeyIfNeeded();
                        return;
                    }
                    cfg.setGateToken(key);
                    if (gateToken != null) gateToken.setText(key);
                    gateKeyPromptShown = false;
                    toast(getString(R.string.gate_key_saved));
                    if (!hasGateDevices()) autoImportGate();
                    pollOnce();
                })
                .setNegativeButton(R.string.update_later, null)
                .show();
    }

    /** Мост отвечает 401/403 и {"error":"auth"}, если ключ неверный или отозван. */
    private static boolean authFailed(Http.Response r) {
        if (r == null) return false;
        if (r.code == 401 || r.code == 403) return true;
        return r.body != null && r.body.contains("\"auth\"");
    }

    private void runIo(Runnable r) {
        if (io == null || io.isShutdown()) return;
        try {
            io.execute(r);
        } catch (Exception ignored) {
        }
    }

    private void toast(String text) {
        if (!isFinishing()) Toast.makeText(this, text, Toast.LENGTH_SHORT).show();
    }

    private int dp(int v) {
        return Ui.dp(this, v);
    }

    private abstract static class SimpleWatcher implements TextWatcher {
        @Override
        public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

        @Override
        public void onTextChanged(CharSequence s, int start, int before, int count) {}
    }
}
