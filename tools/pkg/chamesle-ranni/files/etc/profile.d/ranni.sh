# ranni's settings come before the kde edition's in /etc/xdg. gtk apps put their menus in the menu bar too
case ":$XDG_CONFIG_DIRS:" in
*:/etc/xdg/ranni:*) ;;
*) export XDG_CONFIG_DIRS="/etc/xdg/ranni:${XDG_CONFIG_DIRS:-/etc/xdg}" ;;
esac
export GTK_MODULES="${GTK_MODULES:+$GTK_MODULES:}appmenu-gtk-module"
