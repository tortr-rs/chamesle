// ranni: a menu bar on top with the app's menus, a dock at the bottom
var bar = new Panel
bar.location = "top"
bar.height = 2 * Math.ceil(gridUnit * 1.6 / 2)

var kickoff = bar.addWidget("org.kde.plasma.kickoff")
kickoff.currentConfigGroup = ["General"]
kickoff.writeConfig("icon", "chamesle-start")

bar.addWidget("org.kde.plasma.appmenu")
bar.addWidget("org.kde.plasma.panelspacer")
bar.addWidget("org.kde.plasma.systemtray")

// Sun 25 Oct  13:45
var clock = bar.addWidget("org.kde.plasma.digitalclock")
clock.currentConfigGroup = ["Appearance"]
clock.writeConfig("use24hFormat", 2)
clock.writeConfig("showDate", true)
clock.writeConfig("dateDisplayFormat", "BesideTime")
clock.writeConfig("dateFormat", "custom")
clock.writeConfig("customDateFormat", "ddd d MMM")

var dock = new Panel
dock.location = "bottom"
dock.height = 2 * Math.ceil(gridUnit * 3.2 / 2)
dock.floating = true
dock.lengthMode = "fit"
dock.alignment = "center"
dock.hiding = "dodgewindows"

var tasks = dock.addWidget("org.kde.plasma.icontasks")
tasks.currentConfigGroup = ["General"]
tasks.writeConfig("launchers", ["applications:org.kde.dolphin.desktop", "applications:firefox.desktop",
    "applications:org.chamesle.Store.desktop", "applications:org.kde.konsole.desktop",
    "applications:systemsettings.desktop"])
tasks.writeConfig("iconSpacing", 2)

var desktop = desktopsForActivity(currentActivity())[0]
if (desktop) {
    desktop.wallpaperPlugin = "org.kde.image"
    desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"]
    desktop.writeConfig("Image", "file:///usr/share/wallpapers/Ranni/contents/images/3840x2160.jpg")
}
