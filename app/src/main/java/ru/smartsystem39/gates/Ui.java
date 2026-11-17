package ru.smartsystem39.gates;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Мелкие помощники оформления: dp, скруглённые фоны, ripple, чипы. */
public final class Ui {
    private Ui() {}

    public static int dp(Context c, float v) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v,
                c.getResources().getDisplayMetrics()));
    }

    public static int color(Context c, int res) {
        return c.getColor(res);
    }

    public static GradientDrawable fill(int fill, float radius) {
        GradientDrawable g = new GradientDrawable();
        g.setShape(GradientDrawable.RECTANGLE);
        g.setColor(fill);
        g.setCornerRadius(radius);
        return g;
    }

    public static GradientDrawable stroke(int fill, int strokeColor, float radius, int strokeWidth) {
        GradientDrawable g = fill(fill, radius);
        g.setStroke(strokeWidth, strokeColor);
        return g;
    }

    public static Drawable ripple(int rippleColor, Drawable content, float radius) {
        GradientDrawable mask = new GradientDrawable();
        mask.setShape(GradientDrawable.RECTANGLE);
        mask.setColor(0xFFFFFFFF);
        mask.setCornerRadius(radius);
        return new RippleDrawable(ColorStateList.valueOf(rippleColor), content, mask);
    }

    public static Drawable cardBackground(Context c) {
        int radius = dp(c, 22);
        Drawable content = c.getResources().getDrawable(R.drawable.bg_card, c.getTheme());
        return ripple(0x22FFFFFF, content, radius);
    }

    public static TextView chip(Context c, String label) {
        TextView v = new TextView(c);
        v.setText(label);
        v.setTextSize(13);
        v.setGravity(Gravity.CENTER);
        v.setSingleLine(true);
        v.setEllipsize(TextUtils.TruncateAt.END);
        v.setPadding(dp(c, 6), dp(c, 11), dp(c, 6), dp(c, 11));
        v.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        return v;
    }

    public static void setChipSelected(Context c, TextView v, boolean selected) {
        float radius = Ui.dp(c, 14);
        if (selected) {
            v.setTextColor(Ui.color(c, R.color.accent));
            v.setBackground(ripple(0x33FFFFFF, fill(Ui.color(c, R.color.accent_soft), radius), radius));
        } else {
            v.setTextColor(Ui.color(c, R.color.text_secondary));
            v.setBackground(ripple(0x22FFFFFF,
                    stroke(Ui.color(c, R.color.field), Ui.color(c, R.color.field_stroke), radius, Ui.dp(c, 1)),
                    radius));
        }
    }

    public static LinearLayout.LayoutParams rowLp(Context c) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.bottomMargin = dp(c, 10);
        return lp;
    }

    public static View spacer(Context c, int h) {
        View v = new View(c);
        v.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(c, h)));
        return v;
    }

    public static void margins(View v, int l, int t, int r, int b) {
        if (v.getLayoutParams() instanceof ViewGroup.MarginLayoutParams) {
            ((ViewGroup.MarginLayoutParams) v.getLayoutParams()).setMargins(l, t, r, b);
        }
    }

    /** Красит кнопку и ставит иконку слева — один вид на все действия.
     *  Размер иконки задаём сами: у векторных drawable он иначе крупнее кнопки. */
    public static void styleButton(Context c, Button b, int background, int textColor, int icon) {
        b.setBackgroundResource(background);
        int color = c.getColor(textColor);
        b.setTextColor(color);
        if (icon != 0) {
            Drawable d = c.getResources().getDrawable(icon, c.getTheme()).mutate();
            int size = dp(c, 13);
            d.setBounds(0, 0, size, size);
            b.setCompoundDrawables(d, null, null, null);
            b.setCompoundDrawableTintList(ColorStateList.valueOf(color));
        } else {
            b.setCompoundDrawables(null, null, null, null);
        }
    }
}
