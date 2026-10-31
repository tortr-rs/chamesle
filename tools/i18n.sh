#!/bin/sh
# strings of our apps -> tools/pkg/chamesle-l10n/files/chamesle.pot, and into every language's .po
#   tools/i18n.sh
set -eu
cd "$(dirname "$0")/.."
P=tools/pkg/chamesle-l10n/files
xgettext --from-code=UTF-8 -L Python --keyword=_ --keyword=ngettext:1,2 --add-comments=TRANSLATORS \
    --no-wrap --sort-by-file --package-name=Chamesle --msgid-bugs-address=https://github.com/tortr-rs/chamesle/issues \
    -o $P/chamesle.pot tools/pkg/chamesle-store/files/usr/bin/chamesle-store
for f in $P/*.po; do
    [ -e "$f" ] || continue
    msgmerge -q -U --backup=none --no-wrap "$f" $P/chamesle.pot
done
