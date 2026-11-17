package ru.smartsystem39.gates;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.net.Uri;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextUtils;
import android.text.TextWatcher;
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
    private final Map<String, Card> cards = new HashMap<>();
    private final Map<String, Status> lastStatus = new HashMap<>();
    private final AtomicBoolean inFlight = new AtomicBoolean(false);
    private boolean polling = false;
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
    private View statusDot;
    private ImageButton btnRefresh;
    private EditText haUrl;
    private EditText haToken;
    private EditText gateUrl;
    private EditText gateToken;
    private Button btnGateImport;
    private TextView gateStatus;
    private CheckBox haInsecure;
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
        ImageButton action;
        ImageView icon;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        cfg = new Config(this);
        io = Executors.newSingleThreadExecutor();
        setContentView(R.layout.activity_main);
        bind();
        setupSettings();
        setupNav();
        reloadDevices();
        selectTab(0);
        ui.postDelayed(() -> checkUpdates(true), 1500);
        ui.postDelayed(this::autoImportGate, 900);
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
        gateToken = findViewById(R.id.gateToken);
        btnGateImport = findViewById(R.id.btnGateImport);
        gateStatus = findViewById(R.id.gateStatus);
        haInsecure = findViewById(R.id.haInsecure);
        btnTest = findViewById(R.id.btnTest);
        btnAddDevice = findViewById(R.id.btnAddDevice);
        versionText = findViewById(R.id.versionText);
        updateStatus = findViewById(R.id.updateStatus);
        btnCheckUpdates = findViewById(R.id.btnCheckUpdates);
        btnInstallUpdate = findViewById(R.id.btnInstallUpdate);
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

        gateUrl.setText(cfg.getGateUrl());
        gateToken.setText(cfg.getGateToken());
        gateUrl.addTextChangedListener(new SimpleWatcher() {
            @Override
            public void afterTextChanged(Editable s) {
                cfg.setGateUrl(s.toString().trim());
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
        headerTitle.setText(main ? R.string.title_main : R.string.title_settings);
        statusChip.setVisibility(main ? View.VISIBLE : View.GONE);
        btnRefresh.setVisibility(main ? View.VISIBLE : View.INVISIBLE);

        int accent = getColor(R.color.accent);
        int secondary = getColor(R.color.text_secondary);
        navDevicesIcon.setColorFilter(main ? accent : secondary);
        navDevicesText.setTextColor(main ? accent : secondary);
        navSettingsIcon.setColorFilter(main ? secondary : accent);
        navSettingsText.setTextColor(main ? secondary : accent);
        navDevices.setBackgroundResource(main ? R.drawable.bg_nav_pill : 0);
        navSettings.setBackgroundResource(main ? 0 : R.drawable.bg_nav_pill);

        if (!main) {
            rebuildSettings();
        } else {
            pollOnce();
        }
    }

    private void reloadDevices() {
        devices = cfg.getDevices();
        cards.clear();
        lastStatus.clear();
        rebuildMain();
        rebuildSettings();
        if (devices.isEmpty()) {
            setHeader(getString(R.string.status_no_devices), R.drawable.dot_muted, getColor(R.color.text_secondary));
        } else {
            setHeader(getString(R.string.status_checking), R.drawable.dot_muted, getColor(R.color.text_secondary));
        }
    }

    private void rebuildMain() {
        listMain.removeAllViews();
        cards.clear();
        if (devices.isEmpty()) {
            listMain.addView(buildEmptyView());
            return;
        }

        List<Device> favorites = new ArrayList<>();
        for (Device d : devices) {
            if (d.favorite) favorites.add(d);
        }

        if (favorites.isEmpty()) {
            listMain.addView(buildHint(getString(R.string.favorites_hint)));
        } else {
            listMain.addView(buildSection(getString(R.string.section_favorites)));
            for (Device d : favorites) addCard(d);
        }

        boolean expanded = allExpanded || favorites.isEmpty();
        listMain.addView(buildAllHeader(expanded));
        if (expanded) {
            for (Device d : devices) addCard(d);
        }
    }

    private void addCard(Device d) {
        Card c = buildCard(d);
        cards.put(d.id, c);
        listMain.addView(c.root);
        Status known = lastStatus.get(d.id);
        if (known != null) applyStatus(c, known);
    }

    private TextView buildSection(String text) {
        TextView title = new TextView(this);
        title.setText(text);
        title.setTextColor(getColor(R.color.text_muted));
        title.setTextSize(11);
        title.setAllCaps(true);
        title.setLetterSpacing(0.12f);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(6);
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

    private View buildAllHeader(boolean expanded) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(14), dp(14), dp(14), dp(14));
        row.setBackground(Ui.cardBackground(this));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(4);
        lp.bottomMargin = dp(10);
        row.setLayoutParams(lp);

        TextView title = new TextView(this);
        title.setText(getString(R.string.section_all_count, devices.size()));
        title.setTextColor(getColor(R.color.text_primary));
        title.setTextSize(15);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        title.setLayoutParams(tlp);
        row.addView(title);

        ImageView chevron = new ImageView(this);
        chevron.setLayoutParams(new LinearLayout.LayoutParams(dp(24), dp(24)));
        chevron.setImageResource(R.drawable.ic_chevron);
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

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(16), dp(16), dp(14), dp(16));
        card.setBackground(Ui.cardBackground(this));
        card.setElevation(dp(2));
        card.setLayoutParams(Ui.rowLp(this));
        c.root = card;

        FrameLayout iconBox = new FrameLayout(this);
        LinearLayout.LayoutParams ilp = new LinearLayout.LayoutParams(dp(46), dp(46));
        iconBox.setLayoutParams(ilp);
        iconBox.setBackgroundResource(R.drawable.bg_icon_circle);

        ImageView icon = new ImageView(this);
        FrameLayout.LayoutParams flp = new FrameLayout.LayoutParams(dp(24), dp(24), Gravity.CENTER);
        icon.setLayoutParams(flp);
        icon.setImageResource(Device.typeIcon(d.type));
        icon.setColorFilter(getColor(R.color.bg));
        c.icon = icon;
        iconBox.addView(icon);
        card.addView(iconBox);

        LinearLayout texts = new LinearLayout(this);
        texts.setOrientation(LinearLayout.VERTICAL);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(0,
                ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        tlp.leftMargin = dp(14);
        tlp.rightMargin = dp(10);
        texts.setLayoutParams(tlp);

        TextView name = new TextView(this);
        name.setText(d.name.isEmpty() ? Device.typeLabel(d.type) : d.name);
        name.setTextColor(getColor(R.color.text_primary));
        name.setTextSize(15);
        name.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        name.setSingleLine(false);
        name.setMaxLines(2);
        name.setEllipsize(TextUtils.TruncateAt.END);
        c.name = name;
        texts.addView(name);

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(9), dp(4), dp(10), dp(4));
        row.setBackground(Ui.fill(getColor(R.color.field), dp(999)));
        LinearLayout.LayoutParams rlp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        rlp.topMargin = dp(6);
        row.setLayoutParams(rlp);
        c.pill = row;

        View dot = new View(this);
        dot.setLayoutParams(new LinearLayout.LayoutParams(dp(7), dp(7)));
        dot.setBackgroundResource(R.drawable.dot_muted);
        c.dot = dot;
        row.addView(dot);

        TextView status = new TextView(this);
        LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        slp.leftMargin = dp(7);
        status.setLayoutParams(slp);
        status.setText(R.string.status_checking);
        status.setTextColor(getColor(R.color.text_secondary));
        status.setTextSize(13);
        status.setMaxLines(1);
        status.setEllipsize(TextUtils.TruncateAt.END);
        c.status = status;
        row.addView(status);
        texts.addView(row);
        card.addView(texts);

        ImageButton star = new ImageButton(this);
        star.setLayoutParams(new LinearLayout.LayoutParams(dp(34), dp(34)));
        star.setPadding(dp(7), dp(7), dp(7), dp(7));
        star.setBackgroundResource(R.drawable.bg_circle_ripple);
        star.setImageResource(d.favorite ? R.drawable.ic_star : R.drawable.ic_star_outline);
        star.setColorFilter(getColor(d.favorite ? R.color.warn : R.color.text_muted));
        star.setContentDescription(getString(d.favorite ? R.string.fav_remove : R.string.fav_add));
        star.setOnClickListener(v -> toggleFavorite(d));
        card.addView(star);

        ImageButton action = null;
        if (d.isGate()) {
            LinearLayout dirs = new LinearLayout(this);
            dirs.setOrientation(LinearLayout.VERTICAL);
            if (d.dirIn) dirs.addView(dirButton(d, "in", getString(R.string.dir_in)));
            if (d.dirOut) dirs.addView(dirButton(d, "out", getString(R.string.dir_out)));
            card.addView(dirs);
            c.action = null;
        } else {
            action = new ImageButton(this);
            action.setLayoutParams(new LinearLayout.LayoutParams(dp(46), dp(46)));
            action.setPadding(dp(12), dp(12), dp(12), dp(12));
            action.setImageResource(R.drawable.ic_power);
            action.setColorFilter(getColor(R.color.accent));
            action.setBackground(Ui.ripple(0x33FFFFFF, Ui.fill(getColor(R.color.accent_soft), dp(23)), dp(23)));
            action.setContentDescription(getString(R.string.app_name) + " " + name.getText());
            action.setOnClickListener(v -> onTap(d));
            c.action = action;
            card.addView(action);
        }

        card.setOnClickListener(v -> onTap(d));
        card.setOnLongClickListener(v -> {
            openEditor(d.id);
            return true;
        });

        if (!d.isConfigured() && !d.isGate()) {
            status.setText(R.string.not_configured_hint);
            status.setTextColor(getColor(R.color.text_secondary));
            dot.setBackgroundResource(R.drawable.dot_muted);
            if (action != null) {
                action.setImageResource(R.drawable.ic_settings);
                action.setColorFilter(getColor(R.color.text_secondary));
                action.setBackground(Ui.ripple(0x33FFFFFF, Ui.fill(getColor(R.color.field), dp(23)), dp(23)));
            }
        }
        return c;
    }

    private void applyStatus(Card c, Status s) {
        c.status.setText(s.text);
        int color;
        int dot;
        switch (s.kind) {
            case Status.OPEN:
            case Status.ON:
                color = getColor(R.color.accent);
                dot = R.drawable.dot_green;
                break;
            case Status.MOVING:
                color = getColor(R.color.warn);
                dot = R.drawable.dot_amber;
                break;
            case Status.READY:
                color = getColor(R.color.info);
                dot = R.drawable.dot_blue;
                break;
            case Status.OFFLINE:
                color = getColor(R.color.danger);
                dot = R.drawable.dot_red;
                break;
            case Status.CLOSED:
            case Status.OFF:
            case Status.UNKNOWN:
            default:
                color = getColor(R.color.text_secondary);
                dot = R.drawable.dot_muted;
                break;
        }
        c.status.setTextColor(color);
        c.dot.setBackgroundResource(dot);
        int tint;
        switch (s.kind) {
            case Status.OPEN:
            case Status.ON: tint = R.color.accent_soft; break;
            case Status.MOVING: tint = R.color.warn_soft; break;
            case Status.READY: tint = R.color.info_soft; break;
            case Status.OFFLINE: tint = R.color.danger_soft; break;
            default: tint = R.color.field; break;
        }
        if (c.pill != null) c.pill.setBackground(Ui.fill(getColor(tint), dp(999)));
        if (c.action == null) return;
        if (s.isMoving()) {
            c.action.setImageResource(R.drawable.ic_stop);
            c.action.setColorFilter(getColor(R.color.warn));
            c.action.setBackground(Ui.ripple(0x33FFFFFF, Ui.fill(getColor(R.color.warn_soft), dp(23)), dp(23)));
        } else {
            c.action.setImageResource(R.drawable.ic_power);
            boolean online = s.kind != Status.OFFLINE && s.kind != Status.UNKNOWN;
            c.action.setColorFilter(getColor(online ? R.color.accent : R.color.text_muted));
            c.action.setBackground(Ui.ripple(0x33FFFFFF, Ui.fill(getColor(R.color.accent_soft), dp(23)), dp(23)));
        }
    }

    private Button dirButton(Device d, String dir, String label) {
        Button b = new Button(this);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(78), dp(38));
        lp.bottomMargin = dp(6);
        b.setLayoutParams(lp);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextSize(12);
        b.setTextColor(getColor(R.color.white));
        b.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        b.setBackgroundResource("out".equals(dir) ? R.drawable.btn_out : R.drawable.btn_in);
        b.setCompoundDrawablesWithIntrinsicBounds(
                "out".equals(dir) ? R.drawable.ic_arrow_out : R.drawable.ic_arrow_in, 0, 0, 0);
        b.setCompoundDrawablePadding(dp(4));
        b.setPadding(dp(8), 0, dp(8), 0);
        b.setOnClickListener(v -> onTapDir(d, dir));
        return b;
    }

    private void onTapDir(Device d, String dir) {
        final String base = HaClient.normalizeBase(d.address);
        if (base.isEmpty()) { toast(getString(R.string.status_ha_not_set)); return; }
        runIo(() -> {
            Http.Response r = Http.get(base + "/open?id=" + d.gateId + "&dir=" + dir
                    + "&token=" + Uri.encode(d.gateToken), null, false);
            final String err = r.ok() ? null : (r.error == null ? "HTTP " + r.code : r.error);
            ui.post(() -> {
                toast(err == null ? getString(R.string.cmd_sent) : err);
                pollOnce();
            });
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
        final Card c = cards.get(d.id);
        if (c != null && c.action != null) c.action.setEnabled(false);

        if (Device.SRC_HA.equals(d.source)) {
            final String domain = domainOf(d.entity);
            final String service = serviceFor(domain, lastStatus.get(d.id));
            runIo(() -> {
                HaClient.Result<String> r = new HaClient(cfg.getHaUrl(), cfg.getHaToken(), cfg.haInsecure())
                        .callService(domain, service, d.entity);
                ui.post(() -> {
                    if (c != null && c.action != null) c.action.setEnabled(true);
                    toast(r.error == null ? getString(R.string.cmd_sent) : r.error);
                    pollOnce();
                });
            });
        } else {
            runIo(() -> {
                DirectClient.Result r = DirectClient.toggle(d, cfg.haInsecure());
                ui.post(() -> {
                    if (c != null && c.action != null) c.action.setEnabled(true);
                    toast(r.error == null ? getString(R.string.cmd_sent) : r.error);
                    pollOnce();
                });
            });
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
                if ("locking".equals(state) || "unlocking".equals(state)) {
                    return new Status(Status.MOVING, "Закрывается…");
                }
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
            String error = null;
            int added = 0;
            if (!r.ok()) {
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
                        found.name = name;
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
            final String ferr = error;
            final int fadded = added;
            ui.post(() -> {
                importingGate = false;
                btnGateImport.setEnabled(true);
                if (ferr != null) {
                    gateStatus.setTextColor(getColor(R.color.danger));
                    gateStatus.setText(getString(R.string.gate_error, ferr));
                    if (silent && tab == 0) {
                        setHeader(getString(R.string.gate_unreachable, ferr),
                                R.drawable.dot_red, getColor(R.color.danger));
                    }
                } else {
                    gateStatus.setTextColor(getColor(R.color.accent));
                    gateStatus.setText(getString(R.string.gate_ok, fadded));
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
        icon.setColorFilter(getColor(R.color.bg));
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

        TextView sub = new TextView(this);
        sub.setText(Device.typeLabel(d.type) + " · " + sourceText(d));
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
        del.setImageResource(R.drawable.ic_trash);
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
        icon.setImageResource(R.drawable.ic_gate);
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
        add.setTextColor(getColor(R.color.bg));
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

    private void updateHeader(boolean hasHa, boolean failed) {
        if (devices.isEmpty()) {
            setHeader(getString(R.string.status_no_devices), R.drawable.dot_muted, getColor(R.color.text_secondary));
            return;
        }
        if (hasHa) {
            if (!cfg.hasHa()) {
                boolean entityChosen = false;
                for (Device d : devices) {
                    if (Device.SRC_HA.equals(d.source) && !d.entity.isEmpty()) {
                        entityChosen = true;
                        break;
                    }
                }
                setHeader(entityChosen ? "Укажите адрес и токен HA" : "Настройте подключение",
                        R.drawable.dot_muted, getColor(R.color.text_secondary));
                return;
            }
            if (failed) {
                setHeader(getString(R.string.status_ha_offline), R.drawable.dot_red, getColor(R.color.danger));
            } else {
                setHeader(getString(R.string.status_ha_online), R.drawable.dot_green, getColor(R.color.accent));
            }
            return;
        }
        boolean anyConfigured = false;
        for (Device d : devices) {
            if (d.isConfigured()) {
                anyConfigured = true;
                break;
            }
        }
        if (anyConfigured) {
            setHeader(getString(R.string.status_direct), R.drawable.dot_blue, getColor(R.color.info));
        } else {
            setHeader("Настройте устройства", R.drawable.dot_muted, getColor(R.color.text_secondary));
        }
    }

    private void setHeader(String text, int dotRes, int color) {
        statusText.setText(text);
        statusText.setTextColor(color);
        statusDot.setBackgroundResource(dotRes);
    }

    private void pollOnce() {
        if (io == null || io.isShutdown()) return;
        if (!inFlight.compareAndSet(false, true)) return;
        final List<Device> snapshot = new ArrayList<>(devices);
        final String haUrl = cfg.getHaUrl().trim();
        final String haToken = cfg.getHaToken().trim();
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
                for (Device d : snapshot) {
                    if (Device.SRC_HA.equals(d.source)) continue;
                    if (!d.isConfigured()) {
                        results.put(d.id, new Status(Status.UNKNOWN, "Не настроено"));
                    } else if (d.pulse) {
                        results.put(d.id, new Status(Status.READY, "Готов"));
                    } else {
                        results.put(d.id, DirectClient.status(d, insecure));
                    }
                }
                final boolean fFailed = failed;
                ui.post(() -> {
                    for (Card c : cards.values()) {
                        if (!c.device.isConfigured()) continue;
                        Status s = results.get(c.id);
                        if (s != null) {
                            lastStatus.put(c.id, s);
                            applyStatus(c, s);
                        }
                    }
                    updateHeader(hasHa, fFailed);
                    inFlight.set(false);
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
        startPolling();
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopPolling();
    }

    @Override
    public void onBackPressed() {
        if (tab == 1) {
            selectTab(0);
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        stopPolling();
        ui.removeCallbacksAndMessages(null);
        if (io != null) io.shutdownNow();
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
