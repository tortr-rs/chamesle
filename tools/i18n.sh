#!/bin/sh
# strings of our apps -> tools/pkg/chamesle-l10n/files/chamesle.pot, and into every language's .po
#   tools/i18n.sh
set -eu
cd "$(dirname "$0")/.."
P=tools/pkg/chamesle-l10n/files
O="--from-code=UTF-8 --add-comments=TRANSLATORS --no-wrap --sort-by-file --package-name=Chamesle --msgid-bugs-address=https://github.com/tortr-rs/chamesle/issues"
# the python apps, then the shell ones joined on
xgettext $O -L Python --keyword=_ --keyword=N_ --keyword=ngettext:1,2 -o $P/chamesle.pot \
    tools/pkg/chamesle-store/files/usr/bin/chamesle-store \
    tools/pkg/chamesle-updater/files/usr/bin/chamesle-updater \
    tools/pkg/chamesle-drivers/files/usr/bin/chamesle-drivers \
    overlay/usr/lib/jiggity/firstboot.py overlay/usr/lib/jiggity/ui.py overlay/usr/lib/jiggity/account.py
xgettext $O -j -L Shell --keyword=_ -o $P/chamesle.pot \
    tools/pkg/chamesle-snapshots/files/usr/bin/chamesle-snapshot \
    tools/pkg/chamesle-wine/files/usr/bin/chamesle-exe
# the menu entries' names and descriptions (not their keywords)
D="tools/pkg/chamesle-store/files/usr/share/applications/org.chamesle.Store.desktop
tools/pkg/chamesle-drivers/files/usr/share/applications/org.chamesle.Drivers.desktop
tools/pkg/chamesle-wine/files/usr/share/applications/chamesle-exe.desktop"
xgettext $O -j -L Desktop --keyword= --keyword=Name --keyword=GenericName --keyword=Comment -o $P/chamesle.pot $D
for f in $P/*.po; do
    [ -e "$f" ] || continue
    msgmerge -q -U --backup=none --no-wrap "$f" $P/chamesle.pot
done
# and the translations back into the menu entries, from the english lines alone
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
for f in $P/*.po; do l=$(basename "$f" .po); echo "$l" >> $T/LINGUAS; ln -s "$PWD/$f" $T/; done
for d in $D; do
    grep -v '^[A-Za-z]\+\[' "$d" > $T/in.desktop
    msgfmt --desktop --keyword= --keyword=Name --keyword=GenericName --keyword=Comment --template=$T/in.desktop -d $T -o "$d"
done
