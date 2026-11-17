package ru.smartsystem39.gates;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.graphics.Typeface;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextUtils;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.List;

/** Редактор одного устройства: источник (HA или прямой HTTP), тип и параметры. */
public class DeviceEditActivity extends Activity {

    private static final String[] TYPE_VALUES = {
            Device.TYPE_BARRIER, Device.TYPE_GATE, Device.TYPE_WIDE, Device.TYPE_RELAY
    };
    private static final String[] PROTOCOL_VALUES = {
            Device.P_TASMOTA, Device.P_SHELLY1, Device.P_SHELLY2, Device.P_ESPHOME, Device.P_CUSTOM
    };
    private static final String[] PROTOCOL_LABELS = {
            "Tasmota", "Shelly Gen1", "Shelly Gen2", "ESPHome", "Свой HTTP"
    };

    private Config cfg;
    private Device device;
    private boolean isNew;
    private String selectedEntity = "";
    private String selectedEntityName = "";

    private EditText nameInput;
    private EditText addressInput;
    private EditText channelInput;
    private EditText objectIdInput;
    private EditText openUrlInput;
    private EditText closeUrlInput;
    private EditText statusUrlInput;
    private EditText statusFieldInput;
    private EditText onValueInput;
    private LinearLayout typeRow;
    private LinearLayout sourceRow;
    private LinearLayout cardHa;
    private LinearLayout cardHttp;
    private LinearLayout channelBox;
    private LinearLayout objectIdBox;
    private LinearLayout customBox;
    private CheckBox pulseCheck;
    private CheckBox favoriteCheck;
    private Spinner protocolSpinner;
    private TextView entityValue;
    private TextView protoHint;
    private TextView editTitle;
    private Button btnSave;
    private Button btnDelete;
    private Button btnPickEntity;
    private ImageButton btnBack;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        cfg = new Config(this);
        String id = getIntent().getStringExtra("device_id");
        isNew = true;
        if (id != null && !id.isEmpty()) {
            for (Device d : cfg.getDevices()) {
                if (d.id.equals(id)) {
                    device = d;
                    isNew = false;
                    break;
                }
            }
        }
        if (device == null) {
            device = new Device(Device.newId(), "", Device.TYPE_BARRIER);
            device.source = cfg.hasHa() ? Device.SRC_HA : Device.SRC_HTTP;
        }
        selectedEntity = device.entity == null ? "" : device.entity;

        setContentView(R.layout.activity_device_edit);
        bind();
        populate();
        buildChips();
        setupSpinner();
        setupListeners();
        updateVisibility();
    }

    private void bind() {
        nameInput = findViewById(R.id.nameInput);
        addressInput = findViewById(R.id.addressInput);
        channelInput = findViewById(R.id.channelInput);
        objectIdInput = findViewById(R.id.objectIdInput);
        openUrlInput = findViewById(R.id.openUrlInput);
        closeUrlInput = findViewById(R.id.closeUrlInput);
        statusUrlInput = findViewById(R.id.statusUrlInput);
        statusFieldInput = findViewById(R.id.statusFieldInput);
        onValueInput = findViewById(R.id.onValueInput);
        typeRow = findViewById(R.id.typeRow);
        sourceRow = findViewById(R.id.sourceRow);
        cardHa = findViewById(R.id.cardHa);
        cardHttp = findViewById(R.id.cardHttp);
        channelBox = findViewById(R.id.channelBox);
        objectIdBox = findViewById(R.id.objectIdBox);
        customBox = findViewById(R.id.customBox);
        pulseCheck = findViewById(R.id.pulseCheck);
        favoriteCheck = findViewById(R.id.favoriteCheck);
        protocolSpinner = findViewById(R.id.protocolSpinner);
        entityValue = findViewById(R.id.entityValue);
        protoHint = findViewById(R.id.protoHint);
        editTitle = findViewById(R.id.editTitle);
        btnSave = findViewById(R.id.btnSave);
        btnDelete = findViewById(R.id.btnDelete);
        btnPickEntity = findViewById(R.id.btnPickEntity);
        btnBack = findViewById(R.id.btnBack);
    }

    private void populate() {
        editTitle.setText(isNew ? R.string.edit_new : R.string.edit_title);
        nameInput.setText(device.name);
        entityValue.setText(entityLabel());
        addressInput.setText(device.address);
        channelInput.setText(String.valueOf(device.channel));
        objectIdInput.setText(device.objectId);
        pulseCheck.setChecked(device.pulse);
        favoriteCheck.setChecked(device.favorite);
        openUrlInput.setText(device.openUrl);
        closeUrlInput.setText(device.closeUrl);
        statusUrlInput.setText(device.statusUrl);
        statusFieldInput.setText(device.statusField);
        onValueInput.setText(device.onValue);
        btnDelete.setVisibility(isNew ? View.GONE : View.VISIBLE);
    }

    private void buildChips() {
        typeRow.removeAllViews();
        for (int i = 0; i < TYPE_VALUES.length; i++) {
            final String value = TYPE_VALUES[i];
            TextView chip = Ui.chip(this, Device.typeLabel(value));
            chip.setTextSize(12);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            lp.rightMargin = i < TYPE_VALUES.length - 1 ? dp(6) : 0;
            chip.setLayoutParams(lp);
            chip.setTag(value);
            chip.setOnClickListener(v -> {
                device.type = value;
                refreshChips(typeRow, device.type);
            });
            typeRow.addView(chip);
        }
        refreshChips(typeRow, device.type);

        sourceRow.removeAllViews();
        String[] sources = {Device.SRC_HA, Device.SRC_HTTP};
        String[] labels = {getString(R.string.source_ha), getString(R.string.source_http)};
        for (int i = 0; i < sources.length; i++) {
            final String value = sources[i];
            TextView chip = Ui.chip(this, labels[i]);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0,
                    ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            lp.rightMargin = i < sources.length - 1 ? dp(6) : 0;
            chip.setLayoutParams(lp);
            chip.setTag(value);
            chip.setOnClickListener(v -> {
                device.source = value;
                refreshChips(sourceRow, device.source);
                updateVisibility();
            });
            sourceRow.addView(chip);
        }
        refreshChips(sourceRow, device.source);
    }

    private void refreshChips(LinearLayout row, String selected) {
        for (int i = 0; i < row.getChildCount(); i++) {
            View child = row.getChildAt(i);
            if (child instanceof TextView) {
                Object tag = child.getTag();
                Ui.setChipSelected(this, (TextView) child, tag != null && tag.equals(selected));
            }
        }
    }

    private void setupSpinner() {
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, PROTOCOL_LABELS);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        protocolSpinner.setAdapter(adapter);
        protocolSpinner.setSelection(indexOfProtocol(device.protocol));
        protocolSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                device.protocol = PROTOCOL_VALUES[position];
                updateVisibility();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {}
        });
    }

    private int indexOfProtocol(String protocol) {
        for (int i = 0; i < PROTOCOL_VALUES.length; i++) {
            if (PROTOCOL_VALUES[i].equals(protocol)) return i;
        }
        return 0;
    }

    private void setupListeners() {
        btnBack.setOnClickListener(v -> finish());
        btnSave.setOnClickListener(v -> save());
        btnDelete.setOnClickListener(v -> confirmDelete());
        btnPickEntity.setOnClickListener(v -> pickEntity());
    }

    private void updateVisibility() {
        boolean ha = Device.SRC_HA.equals(device.source);
        cardHa.setVisibility(ha ? View.VISIBLE : View.GONE);
        cardHttp.setVisibility(ha ? View.GONE : View.VISIBLE);

        boolean custom = Device.P_CUSTOM.equals(device.protocol);
        customBox.setVisibility(custom ? View.VISIBLE : View.GONE);
        pulseCheck.setVisibility(custom ? View.GONE : View.VISIBLE);

        boolean relay = Device.P_TASMOTA.equals(device.protocol)
                || Device.P_SHELLY1.equals(device.protocol)
                || Device.P_SHELLY2.equals(device.protocol);
        channelBox.setVisibility(relay ? View.VISIBLE : View.GONE);
        objectIdBox.setVisibility(Device.P_ESPHOME.equals(device.protocol) ? View.VISIBLE : View.GONE);
        protoHint.setText(hintFor(device.protocol));
    }

    private String hintFor(String protocol) {
        switch (protocol) {
            case Device.P_SHELLY1:
                return "Shelly Gen1: адрес контроллера, канал — номер реле (0 — первое).";
            case Device.P_SHELLY2:
                return "Shelly Gen2/Plus: адрес контроллера, канал — id переключателя (обычно 0).";
            case Device.P_ESPHOME:
                return "ESPHome web_server: адрес, ID — имя переключателя из YAML (switch: … id: gate).";
            case Device.P_CUSTOM:
                return "Свой HTTP: вызывается URL открытия, при известном статусе — URL закрытия. Статус необязателен.";
            default:
                return "Tasmota: адрес контроллера, команда Power TOGGLE. Для каналов 1+ — Power1, Power2…";
        }
    }

    private void save() {
        String name = nameInput.getText().toString().trim();
        if (name.isEmpty()) {
            toast(getString(R.string.error_name));
            nameInput.requestFocus();
            return;
        }
        device.name = name;
        device.favorite = favoriteCheck.isChecked();

        if (Device.SRC_HA.equals(device.source)) {
            if (selectedEntity.isEmpty()) {
                toast(getString(R.string.error_entity));
                return;
            }
            device.entity = selectedEntity;
        } else {
            String address = normalize(addressInput.getText().toString());
            if (address.isEmpty()) {
                toast(getString(R.string.error_address));
                addressInput.requestFocus();
                return;
            }
            device.address = address;

            if (Device.P_CUSTOM.equals(device.protocol)) {
                device.openUrl = normalize(openUrlInput.getText().toString());
                if (device.openUrl.isEmpty()) {
                    toast(getString(R.string.error_open_url));
                    openUrlInput.requestFocus();
                    return;
                }
                device.closeUrl = normalize(closeUrlInput.getText().toString());
                device.statusUrl = normalize(statusUrlInput.getText().toString());
                device.statusField = statusFieldInput.getText().toString().trim();
                String on = onValueInput.getText().toString().trim();
                device.onValue = on.isEmpty() ? "ON" : on;
            } else {
                device.openUrl = "";
                device.closeUrl = "";
                device.statusUrl = "";
                device.statusField = "";
            }

            if (Device.P_ESPHOME.equals(device.protocol)) {
                device.objectId = objectIdInput.getText().toString().trim();
                if (device.objectId.isEmpty()) {
                    toast(getString(R.string.error_object_id));
                    objectIdInput.requestFocus();
                    return;
                }
            }

            int ch = 0;
            try {
                ch = Integer.parseInt(channelInput.getText().toString().trim());
            } catch (Exception ignored) {
            }
            device.channel = Math.max(0, ch);
            device.pulse = pulseCheck.isChecked();
        }

        if (device.id == null || device.id.isEmpty()) device.id = Device.newId();
        cfg.upsert(device);
        toast(getString(R.string.saved));
        finish();
    }

    private String normalize(String raw) {
        String s = raw == null ? "" : raw.trim();
        if (s.isEmpty()) return "";
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://" + s;
        while (s.endsWith("/")) s = s.substring(0, s.length() - 1);
        return s;
    }

    private void confirmDelete() {
        if (isNew) return;
        new AlertDialog.Builder(this)
                .setTitle(R.string.delete_title)
                .setMessage(getString(R.string.delete_text,
                        device.name.isEmpty() ? Device.typeLabel(device.type) : device.name))
                .setNegativeButton(R.string.cancel, null)
                .setPositiveButton(R.string.delete, (dialog, which) -> {
                    cfg.delete(device.id);
                    finish();
                })
                .show();
    }

    private String entityLabel() {
        if (selectedEntity.isEmpty()) return getString(R.string.no_entity);
        if (selectedEntityName == null || selectedEntityName.isEmpty()) return selectedEntity;
        return selectedEntityName + "\n" + selectedEntity;
    }

    private void pickEntity() {
        final String url = cfg.getHaUrl().trim();
        final String token = cfg.getHaToken().trim();
        if (url.isEmpty() || token.isEmpty()) {
            toast(getString(R.string.ha_not_ready));
            return;
        }
        final ProgressDialog progress = ProgressDialog.show(this, "",
                getString(R.string.loading), true, false);
        new Thread(() -> {
            final HaClient.Result<List<HaClient.State>> r =
                    new HaClient(url, token, cfg.haInsecure()).states();
            runOnUiThread(() -> {
                if (isFinishing()) {
                    progress.dismiss();
                    return;
                }
                progress.dismiss();
                if (r.error != null) {
                    toast(r.error);
                } else {
                    showEntityDialog(r.value);
                }
            });
        }, "ha-states").start();
    }

    private void showEntityDialog(List<HaClient.State> states) {
        final List<HaClient.State> allowed = new ArrayList<>();
        for (HaClient.State s : states) {
            String domain = s.id.contains(".") ? s.id.substring(0, s.id.indexOf('.')) : "";
            if (domain.equals("cover") || domain.equals("switch") || domain.equals("button")
                    || domain.equals("script") || domain.equals("input_boolean")
                    || domain.equals("lock")) {
                allowed.add(s);
            }
        }
        if (allowed.isEmpty()) {
            toast("В Home Assistant нет подходящих сущностей");
            return;
        }
        allowed.sort((a, b) -> a.name.compareToIgnoreCase(b.name));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16), dp(8), dp(16), dp(4));

        EditText search = new EditText(this);
        search.setHint(R.string.search_hint);
        search.setSingleLine(true);
        search.setBackgroundResource(R.drawable.bg_field);
        search.setTextColor(getColor(R.color.text_primary));
        search.setHintTextColor(getColor(R.color.text_muted));
        search.setTextSize(14);
        search.setPadding(dp(14), dp(10), dp(14), dp(10));
        root.addView(search, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        final EntityAdapter adapter = new EntityAdapter(allowed);
        ListView list = new ListView(this);
        list.setAdapter(adapter);
        list.setDivider(null);
        LinearLayout.LayoutParams llp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(340));
        llp.topMargin = dp(10);
        root.addView(list, llp);

        final AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(R.string.pick_entity_title)
                .setView(root)
                .setNegativeButton(R.string.cancel, null)
                .create();

        search.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {}

            @Override
            public void afterTextChanged(Editable s) {
                adapter.filter(s.toString());
            }
        });

        list.setOnItemClickListener((parent, view, position, id) -> {
            HaClient.State s = adapter.getItem(position);
            if (s != null) {
                selectedEntity = s.id;
                selectedEntityName = s.name;
                entityValue.setText(entityLabel());
                if (nameInput.getText().toString().trim().isEmpty()) {
                    nameInput.setText(s.name);
                }
            }
            dialog.dismiss();
        });
        dialog.show();
    }

    private final class EntityAdapter extends BaseAdapter {
        private final List<HaClient.State> all;
        private List<HaClient.State> items;

        EntityAdapter(List<HaClient.State> all) {
            this.all = all;
            this.items = new ArrayList<>(all);
        }

        void filter(String query) {
            String q = query == null ? "" : query.trim().toLowerCase();
            if (q.isEmpty()) {
                items = new ArrayList<>(all);
            } else {
                List<HaClient.State> out = new ArrayList<>();
                for (HaClient.State s : all) {
                    if (s.name.toLowerCase().contains(q) || s.id.toLowerCase().contains(q)) {
                        out.add(s);
                    }
                }
                items = out;
            }
            notifyDataSetChanged();
        }

        @Override
        public int getCount() {
            return items.size();
        }

        @Override
        public HaClient.State getItem(int position) {
            return items.get(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            LinearLayout row = new LinearLayout(DeviceEditActivity.this);
            row.setOrientation(LinearLayout.VERTICAL);
            row.setPadding(dp(4), dp(12), dp(4), dp(12));

            HaClient.State s = items.get(position);
            TextView name = new TextView(DeviceEditActivity.this);
            name.setText(s.name);
            name.setTextColor(getColor(R.color.text_primary));
            name.setTextSize(15);
            name.setSingleLine(true);
            name.setEllipsize(TextUtils.TruncateAt.END);
            row.addView(name);

            TextView id = new TextView(DeviceEditActivity.this);
            id.setText(s.id);
            id.setTextColor(getColor(R.color.text_muted));
            id.setTextSize(12);
            id.setSingleLine(true);
            id.setEllipsize(TextUtils.TruncateAt.END);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.topMargin = dp(3);
            id.setLayoutParams(lp);
            row.addView(id);
            return row;
        }
    }

    private void toast(String text) {
        Toast.makeText(this, text, Toast.LENGTH_SHORT).show();
    }

    private int dp(int v) {
        return Ui.dp(this, v);
    }
}
