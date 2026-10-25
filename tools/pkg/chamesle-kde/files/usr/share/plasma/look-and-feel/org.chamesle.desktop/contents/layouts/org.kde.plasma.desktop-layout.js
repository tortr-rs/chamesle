// the chamesle taskbar: start menu, pinned apps and open windows, tray and clock, like windows
var panel = new Panel
panel.location = "bottom"
panel.height = 2 * Math.ceil(gridUnit * 2.4 / 2)
panel.floating = true

var kickoff = panel.addWidget("org.kde.plasma.kickoff")
kickoff.currentConfigGroup = ["General"]
kickoff.writeConfig("icon", "chamesle-start")

var tasks = panel.addWidget("org.kde.plasma.icontasks")
tasks.currentConfigGroup = ["General"]
tasks.writeConfig("launchers", ["applications:org.kde.dolphin.desktop", "applications:firefox.desktop",
    "applications:org.chamesle.Store.desktop", "applications:org.kde.konsole.desktop"])

panel.addWidget("org.kde.plasma.marginsseparator")
panel.addWidget("org.kde.plasma.systemtray")

// 24-hour time with the date under it: 13:45 and 24 Oct 2026
var clock = panel.addWidget("org.kde.plasma.digitalclock")
clock.currentConfigGroup = ["Appearance"]
clock.writeConfig("use24hFormat", 2)
clock.writeConfig("dateFormat", "custom")
clock.writeConfig("customDateFormat", "d MMM yyyy")


var desktop = desktopsForActivity(currentActivity())[0]
if (desktop) {
    desktop.wallpaperPlugin = "org.kde.image"
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"]
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/Chamesle/contents/images/3840x2160.jpg")
}
