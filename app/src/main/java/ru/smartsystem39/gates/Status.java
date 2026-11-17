package ru.smartsystem39.gates;

/** Состояние устройства для карточки на главном экране. */
public final class Status {
    public static final int READY = 0;
    public static final int OPEN = 1;
    public static final int CLOSED = 2;
    public static final int MOVING = 3;
    public static final int ON = 4;
    public static final int OFF = 5;
    public static final int OFFLINE = 6;
    public static final int UNKNOWN = 7;

    public final int kind;
    public final String text;

    public Status(int kind, String text) {
        this.kind = kind;
        this.text = text;
    }

    public boolean isMoving() {
        return kind == MOVING;
    }

    public boolean isOpenish() {
        return kind == OPEN || kind == ON;
    }
}
