#!/usr/bin/env bash
# Сборка APK без Gradle: aapt2 -> javac -> d8 -> zipalign -> apksigner.
set -euo pipefail

ROOT=/home/dsh/projects
PROJ=$ROOT/gates
SDK=$ROOT/tools/sdk
BT=$(ls -d "$SDK"/build-tools/* | head -1)
AJ=$SDK/platforms/android-34/android.jar
JAVA_HOME=$ROOT/tools/jdk
JAVAC=$JAVA_HOME/bin/javac
export PATH="$JAVA_HOME/bin:$PATH"
KEYTOOL=$JAVA_HOME/bin/keytool

VERSION_CODE=$(grep -o 'android:versionCode="[0-9]*"' "$PROJ/AndroidManifest.xml" | grep -o '[0-9]*')
VERSION_NAME=$(grep -o 'android:versionName="[^"]*"' "$PROJ/AndroidManifest.xml" | sed 's/.*="//; s/"$//')
OUT=$PROJ/build

rm -rf "$OUT"
mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex" "$PROJ/dist"

echo "== aapt2 compile"
"$BT/aapt2" compile --dir "$PROJ/app/src/main/res" -o "$OUT/res.zip"

echo "== aapt2 link"
"$BT/aapt2" link \
  -o "$OUT/unsigned.apk" \
  -I "$AJ" \
  --manifest "$PROJ/AndroidManifest.xml" \
  -R "$OUT/res.zip" \
  --java "$OUT/gen" \
  --min-sdk-version 26 \
  --target-sdk-version 34 \
  --auto-add-overlay \
  -A "$PROJ/app/src/main/assets" \
  --version-code "$VERSION_CODE" \
  --version-name "$VERSION_NAME"

echo "== javac"
find "$PROJ/app/src/main/java" "$OUT/gen" -name '*.java' > "$OUT/sources.txt"
"$JAVAC" -source 8 -target 8 -encoding UTF-8 \
  -classpath "$AJ" \
  -d "$OUT/classes" \
  @"$OUT/sources.txt" > "$OUT/javac.log" 2>&1 || { cat "$OUT/javac.log"; exit 1; }
grep -v "bootstrap class path" "$OUT/javac.log" || true

echo "== d8"
find "$OUT/classes" -name '*.class' > "$OUT/classes.txt"
"$BT/d8" --lib "$AJ" --min-api 26 --output "$OUT/dex" @"$OUT/classes.txt"

echo "== package"
( cd "$OUT/dex" && zip -q "$OUT/unsigned.apk" classes.dex )

echo "== zipalign + sign"
KS=$PROJ/release.keystore
if [ ! -f "$KS" ]; then
  "$KEYTOOL" -genkeypair -keystore "$KS" -storepass 'Vorota2026!' -keypass 'Vorota2026!' \
    -alias vorota -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Vorota, O=DSH, C=RU" >/dev/null 2>&1
fi
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass 'pass:Vorota2026!' --key-pass 'pass:Vorota2026!' \
  --out "$PROJ/dist/Vorota-$VERSION_NAME.apk" "$OUT/aligned.apk"

ls -lh "$PROJ/dist/Vorota-$VERSION_NAME.apk"
"$BT/aapt2" dump badging "$PROJ/dist/Vorota-$VERSION_NAME.apk" | head -4
echo "BUILD OK"
