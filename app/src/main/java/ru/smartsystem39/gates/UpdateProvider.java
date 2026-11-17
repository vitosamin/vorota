package ru.smartsystem39.gates;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;

/** Отдаёт скачанный APK установщику по content:// (без FileProvider из AndroidX). */
public class UpdateProvider extends ContentProvider {

    public static final String AUTHORITY = "ru.smartsystem39.gates.updates";

    public static File updateDir(Context context) {
        File dir = context.getExternalFilesDir("updates");
        if (dir == null) dir = new File(context.getFilesDir(), "updates");
        if (!dir.exists()) dir.mkdirs();
        return dir;
    }

    public static Uri uriFor(File file) {
        return new Uri.Builder()
                .scheme("content")
                .authority(AUTHORITY)
                .appendPath(file.getName())
                .build();
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    private File fileFor(Uri uri) {
        String name = uri.getLastPathSegment();
        if (name == null || name.contains("/") || name.contains("..")) return null;
        return new File(updateDir(getContext()), name);
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection,
                        String[] selectionArgs, String sortOrder) {
        File f = fileFor(uri);
        if (f == null || !f.exists()) return null;
        if (projection == null) {
            projection = new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE};
        }
        MatrixCursor cursor = new MatrixCursor(projection, 1);
        Object[] row = new Object[projection.length];
        for (int i = 0; i < projection.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(projection[i])) {
                row[i] = f.getName();
            } else if (OpenableColumns.SIZE.equals(projection[i])) {
                row[i] = f.length();
            }
        }
        cursor.addRow(row);
        return cursor;
    }

    @Override
    public String getType(Uri uri) {
        return "application/vnd.android.package-archive";
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        File f = fileFor(uri);
        if (f == null || !f.exists()) throw new FileNotFoundException(uri.toString());
        return ParcelFileDescriptor.open(f, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }
}
