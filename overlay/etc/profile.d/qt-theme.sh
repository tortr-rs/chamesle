# Qt apps follow the GTK theme, so they look like everything else. not in plasma: it's Qt itself, and with this
# it takes its fonts, colours and icons from GTK instead of its own settings
case "${DESKTOP_SESSION:-}:${XDG_CURRENT_DESKTOP:-}" in
    plasma*|*KDE*) ;;
    *) [ -n "$QT_QPA_PLATFORMTHEME" ] || export QT_QPA_PLATFORMTHEME=gtk3 ;;
esac
