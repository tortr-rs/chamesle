# play's settings come before the kde edition's in /etc/xdg
case ":$XDG_CONFIG_DIRS:" in
*:/etc/xdg/play:*) ;;
*) export XDG_CONFIG_DIRS="/etc/xdg/play:${XDG_CONFIG_DIRS:-/etc/xdg}" ;;
esac
