#!/usr/bin/env bash
# Локальные JVM-тесты: тестовый Http никогда не обращается к сети.
# Не собирает APK и не изменяет/удаляет build/.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
JDK=${JAVA_HOME:-/home/dsh/projects/tools/jdk}
ANDROID_JAR=${ANDROID_JAR:-/home/dsh/projects/tools/sdk/platforms/android-34/android.jar}
JSON_JAR=${JSON_JAR:-$ROOT/tools/test/json.jar}
OUT=$(mktemp -d "${TMPDIR:-/tmp}/gates-offline-test.XXXXXX")
SRC="$ROOT/app/src/main/java/ru/smartsystem39/gates"
TEST="$ROOT/tools/test/offline/ru/smartsystem39/gates"
mkdir -p "$OUT/gen/ru/smartsystem39/gates" "$OUT/production" "$OUT/test"
# Нужен только набор идентификаторов ресурсов для компиляции Android-классов.
python3 - "$SRC" "$OUT/gen/ru/smartsystem39/gates/R.java" <<'PY'
import pathlib, re, sys
src, out = map(pathlib.Path, sys.argv[1:])
names = {}
for filename in ('Device.java', 'Status.java', 'DirectClient.java', 'DeviceEditActivity.java', 'Config.java', 'Ui.java', 'HaClient.java'):
    text = (src / filename).read_text(encoding='utf-8')
    for kind, name in re.findall(r'(?<!android\.)\bR\.(\w+)\.(\w+)', text):
        names.setdefault(kind, set()).add(name)
with out.open('w', encoding='utf-8') as f:
    f.write('package ru.smartsystem39.gates; public final class R {\n')
    for kind, fields in sorted(names.items()):
        f.write('public static final class ' + kind + ' {\n')
        for i, field in enumerate(sorted(fields), 1):
            f.write('public static final int ' + field + ' = ' + str(i) + ';\n')
        f.write('}\n')
    f.write('}\n')
PY
SOURCES=("$OUT/gen/ru/smartsystem39/gates/R.java" "$SRC/Device.java" "$SRC/Status.java"
         "$SRC/DirectClient.java" "$SRC/DeviceEditActivity.java" "$SRC/Config.java"
         "$SRC/Ui.java" "$SRC/HaClient.java")
"$JDK/bin/javac" -encoding UTF-8 -source 8 -target 8 -classpath "$JSON_JAR:$ANDROID_JAR" \
    -d "$OUT/production" "${SOURCES[@]}" "$SRC/Http.java"
"$JDK/bin/javac" -encoding UTF-8 -source 8 -target 8 -classpath "$JSON_JAR:$ANDROID_JAR" \
    -d "$OUT/test" "${SOURCES[@]}" "$TEST/Http.java" "$TEST/DirectClientOfflineTest.java"
"$JDK/bin/java" -cp "$OUT/test:$JSON_JAR:$ANDROID_JAR" ru.smartsystem39.gates.DirectClientOfflineTest
printf 'Classes left in %s\n' "$OUT"
