"""
Translations for the Tello BCI Controller UI.

Same idea as the i18n table in emotiv-brain-light: every user-facing string is a
key, and `t()` turns it into a sentence in the currently selected language.

Widgets register themselves with `bind()` instead of being given a finished
string, so switching language at runtime only means walking the registry and
re-applying every key. Anything that is not registered (the log terminal, the
raw Cortex stream dumps) stays as-is.
"""

import re

I18N = {
    "en": {
        "lang.name": "English",

        # ── Shell ────────────────────────────────────────────────────────────
        "app.title": "Tello BCI Controller",
        "btn.settings": "⚙ Configurations",
        "header.language": "🌐 Language",

        # ── Step 1 · authentication ──────────────────────────────────────────
        "auth.title": "Connection problem",
        "auth.intro":
            "The app could not reach EMOTIV Cortex. Work through the checks "
            "below — the credentials at the bottom are only needed if support "
            "has asked you to change them.",
        "auth.check_launcher":
            "1. Is EMOTIV Launcher running and signed in? Start it, then press "
            "Retry Connection.",
        "auth.check_approved":
            "2. Has this application been approved? EMOTIV Launcher shows an "
            "approval prompt the first time — approve it, then press Retry "
            "Connection.",
        "auth.reason": "Reported problem: {detail}",
        "auth.group": "Credentials (rarely the problem)",
        "auth.checks_group": "Check these first",
        "auth.client_id": "Client ID:",
        "auth.client_secret": "Client Secret:",
        "auth.simulate": "Simulation Mode (Test UI without headset)",
        "auth.auto_connect": "Connect automatically on startup",
        "auth.auto_connect.tip":
            "Once a Client ID and Secret are saved, skip this screen and start "
            "connecting as soon as the app opens.",
        "auth.connect": "Authenticate",
        "auth.retry": "Retry Connection",
        "auth.retrying": "Reconnecting…",
        "auth.logs": "BCI Connection Logs:",
        "auth.log_file": "Full log file: {path}",

        # ── Step 2 · headset ─────────────────────────────────────────────────
        "headset.title": "Step 1: Select Your Headset",
        "headset.tagline": "Fly a drone with your mind. Pick the headset you are wearing to begin.",
        "headset.group": "Available Headsets",
        "headset.awaiting_auth": "— awaiting authentication —",
        "headset.connect": "Connect Headset",
        "headset.connecting_btn": "⏳ Connecting...",
        "headset.none_found": "⚠️ No headsets found",
        "headset.count": "{count} found",
        "hstatus.discovered": "Ready to connect",
        "hstatus.connected": "Connected",
        "hstatus.connecting": "Connecting…",
        "hstatus.discovering": "Searching…",
        "headset.back": "⬅ Back to Auth",

        # ── Live tuning on the simulator screen ──────────────────────────────
        "tune.mental": "Mental commands",
        "tune.mental_waiting":
            "Load a trained profile to tune how easily each command fires.",

        "retrain.button": "♻ Reset & Retrain",
        "retrain.tip": "Erase this profile's training and go through it again",
        "retrain.title": "Reset the training?",
        "retrain.body":
            "Every trained action in \u201c{profile}\u201d will be erased, including the "
            "neutral baseline, and you will go through training again from the "
            "signal check. The profile itself is kept.",
        "retrain.confirm": "Erase and retrain",

        "common.cancel": "Cancel",

        "log.mc_sensitivity": "Mental command sensitivity set to {values}.",
        "log.no_profile_to_retrain": "Load a trained profile before retraining.",

        "headset.refresh": "🔄 Refresh",
        "headset.refresh.tip": "Re-scan for headsets and reload the list from Cortex",
        "headset.refreshing": "⏳ Scanning…",

        "profile.deleted": "Profile '{profile}' deleted.",
        "profile.reset_done": "Training erased for '{profile}'.",

        "log.auto_connecting": "Saved credentials found — connecting automatically.",
        "log.refreshing_headsets": "Re-scanning for headsets…",
        "log.profile_deleting": "Deleting profile '{profile}'…",
        "log.profile_deleted": "Profile '{profile}' deleted.",
        "log.profile_resetting": "Erasing training for '{profile}'…",
        "log.profile_reset": "Training erased for '{profile}'.",

        "badge.bci_active": "🟢 BCI: Active",
        "badge.profile_loaded": "🟢 🧠 Profile '{profile}' loaded. Ready for flight!",

        # ── Step 3 · profile ─────────────────────────────────────────────────
        "profile.title": "Step 2: Training Profile",
        "profile.group": "Training Profile",
        "profile.label": "Profile:",
        "profile.refresh": "🔄 Refresh",
        "profile.refresh.tip": "Re-fetch profile list from Cortex",
        "profile.connect_first": "— connect headset first —",
        "profile.load": "🧠 Load Selected Profile",
        "profile.loading_btn": "⏳ Loading...",
        "profile.hint": "Create a profile with your name, then train it.",
        "profile.create_label": "Enter your name and train:",
        "profile.new_placeholder": "Your name...",
        "profile.create_train": "🧠 Create & Train",
        "profile.none_found": "⚠️ No profiles found",
        "profile.none_hint": "No training profiles found. Create one in EMOTIV Launcher.",
        "profile.available": "{count} profile(s) available — select one and click Load.",
        "profile.selected": "Profile '{profile}' selected. Ready.",
        "profile.session_active": "Session active. Select a profile and click Load.",
        "profile.back": "⬅ Back to Headsets",
        "profile.next": "Next: Test Controls ➔",

        # ── EMOTIV Launcher approval banner ──────────────────────────────────
        "access.title": "EMOTIV Launcher Approval Required",
        "access.steps": (
            "1. Open the <b>EMOTIV Launcher</b> app on your computer.\n"
            "2. Look for a permission request notification from this application.\n"
            "3. Click <b>Allow</b> to grant access.\n"
            "4. Then press <b>Retry</b> below."
        ),
        "access.retry": "🔄 I've approved — Retry",
        "access.rejected_title": "Access was declined",
        "access.rejected_body":
            "This application was declined in EMOTIV Launcher, so it cannot read "
            "the headset. Open EMOTIV Launcher, approve this application, then "
            "press Retry.",
        "access.waiting": "Waiting for approval in EMOTIV Launcher…",
        "access.checking": "Checking whether this application is approved…",
        "access.granted": "Approved by EMOTIV Launcher.",
        "access.default_msg": (
            "Access not granted. Please open EMOTIV Launcher and approve this application."
        ),

        # ── EEG quality check ────────────────────────────────────────────────
        "eq.title": "EEG Signal Quality Check",
        "eq.subtitle": "Ensure all sensors show good contact quality before training.",
        "eq.overall_waiting": "Overall Signal: Waiting...",
        "eq.overall": "Sensor contact: {quality} ({value}%)",
        "quality.unknown_state": "Waiting…",
        "eq.group": "Sensor Contact Quality",
        "eq.waiting_data": "Waiting for sensor data...",
        "eq.ok": "✅ Signal quality is sufficient for training.",
        "dash.battery": "Drone Batt: {value}%",
        "dash.battery_empty": "Drone Batt: —",
        "dash.camera": "📹 Live Camera Feed",
        "dash.controls": "🕹️ Flight & Controls",
        "dash.disconnect": "🔌 Disconnect & Quit",
        "dash.drone_connected": "🟢 Drone: Connected",
        "dash.drone_sim": "🟡 Drone: Simulating",
        "dash.emergency": "⛔ EMERGENCY",
        "dash.headset": "Headset: {battery}% | Sig: {signal}/4",
        "dash.headset_empty": "Headset: —",
        "dash.height": "Height: {value}cm",
        "dash.height_empty": "Height: —",
        "dash.hud": "📺 Fullscreen HUD",
        "dash.land": "🛬 Land",
        "dash.log": "📟 Log",
        "dash.mc": "🧠 MC: {action}",
        "dash.mc_none": "🧠 MC: None",
        "dash.recenter": "🎯 Recenter",
        "dash.system": "System",
        "dash.takeoff": "🚀 Take Off",
        "dash.telemetry": "📊 Telemetry",
        "dash.temp": "Temp: {value}°C",
        "dash.temp_empty": "Temp: —",
        "drone.back": "⬅ Back to Test",
        "drone.connect": "Connect to Drone",
        "drone.connected": "Drone connected successfully! Battery: {battery}%",
        "drone.connecting": "Connecting to Tello WiFi...",
        "drone.failed": "Connection failed: {detail}",
        "drone.launch": "Launch Flight Dashboard 🚀",
        "drone.ready": "Ready to connect.",
        "drone.sim_skip": "Simulation mode. Skipping real drone connection.",
        "drone.subtitle": "Ensure you are connected to the drone's WiFi network before continuing.",
        "drone.title": "Step 4: Connect to DJI Tello",
        "eq.back": "⬅ Back to Profiles",
        "eq.bad": "⚠️ Improve sensor contact before training. Adjust the headset.",
        "eq.next": "Start Training ➔",
        "quality.bad": "Bad",
        "quality.fair": "Fair",
        "quality.good": "Good",
        "quality.none": "No Signal",
        "quality.poor": "Poor",
        "quality.short_unknown": "?",
        "quality.unknown": "Unknown ({value})",
        "quality.very_bad": "Very Bad",
        "sim.altitude": "ALT {alt}m",
        "sim.esc_hint": "Press ESC to exit fullscreen",
        "sim.mental_command": "🧠 {action}",
        "sim.readout": "ALT {alt}m   ·   SPD {spd}",
        "sim.score": "🏆 {score}",
        "test.back": "⬅ Back",
        "test.next": "Next: Real Drone Setup ➔",
        "test.recenter": "🎯 Recenter Headset",
        "test.state_group": "Simulator",
        "test.title": "Step 3: Fly the Simulator",
        "train.accept": "Accept",
        "train.accepting": "Accepting training...",
        "train.complete": "All training complete! Saving profile...",
        "train.failed": "Training Failed! Poor data quality.",
        "train.finish": "Finish & Go to Test Controls",
        "train.abandon": "⬅ Start over — back to headsets",
        "train.abandon.tip": "Stops this training and releases the headset for the next person.",
        "log.training_abandoned": "Training abandoned; releasing the headset.",
        "train.finishing": "Finishing up...",
        "train.get_ready": "Get ready...",
        "train.neutral.subtitle": "Relax and keep your mind clear. The drone should stay still.",
        "train.neutral.title": "Training: Neutral Baseline",
        "train.push.subtitle": "Focus on the drone. Imagine pushing it forward with your mind.",
        "train.push.title": "Training: Push Command (Forward)",
        "train.recording": "Recording... {seconds}s remaining",
        "train.reject": "Reject (Retry)",
        "train.retry": "Retry",
        "train.retrying": "Retrying training...",
        "train.succeeded": "Training Succeeded! Good data quality.",
        "train.waiting": "Waiting for training to start...",
        "droneaction.FlipRight": "Flip right",
        "droneaction.MoveForward": "Forward",
        "droneaction.MoveBack": "Back",
        "droneaction.MoveLeft": "Left",
        "droneaction.MoveRight": "Right",
        "droneaction.MoveUp": "Up",
        "droneaction.MoveDown": "Down",

        # ── How to fly (simulator screen + in-game overlay) ───────────────────
        "howto.recenter": "Sitting comfortably? Press Recenter to make your current head position the new straight-ahead.",
        "howto.overlay_steer": "Turn your head to steer",
        "howto.overlay_forward": "Think “{action}” to fly forward",
        "howto.overlay_rings": "Fly through the rings — 10 points each",

        # ── Congratulations on the result screen ─────────────────────────────
        "game.congrats_first": "🥇 Congratulations — you are in 1st place!",
        "game.congrats_podium": "🎉 Congratulations — you made the podium in {rank} place!",
        "game.congrats_ranked": "Nice flying — you finished in {rank} place out of {total}!",
        "game.congrats_only": "🥇 Congratulations — you set the first score!",
        "game.mind_message": "And you did it using nothing but your mind. 🧠",
        "game.ordinal_1": "1st", "game.ordinal_2": "2nd", "game.ordinal_3": "3rd",
        "game.ordinal_n": "{n}th",

        # ── Contact-quality head map ─────────────────────────────────────────
        "eq.headmap_group": "Sensor positions (10–20 system)",
        "eq.headmap_hint":
            "Each dot is one sensor, drawn where it sits on your head — nose at the top. "
            "Green means good contact; red means it needs adjusting.",
        "eq.headmap_front": "FRONT",
        "eq.headmap_back": "BACK",
        "eq.headmap_waiting": "Waiting for the headset…",
        "eq.legend": "Contact:",
        "hud.no_signal": "NO CAMERA SIGNAL",
        "hud.esc": "ESC TO EXIT",

        "cue.neutral": "Relax — let the drone hover",
        "cue.push": "Push the drone forward",

        # ── Ring run / leaderboard ───────────────────────────────────────────
        "game.group": "🏁 Ring Run — {seconds} seconds",
        "game.name_placeholder": "Your name",
        "game.playing_as": "Playing as",
        "game.no_profile": "— train a profile first —",
        "game.start": "▶ Start Run",
        "game.running": "Run in progress…",
        "game.get_ready": "Get Ready!",
        "game.go": "Go!",
        "game.show_leaderboard": "🏆 Show Leaderboard",
        "game.timer": "{seconds}s",
        "game.idle_hint": "Press Start Run to begin a timed round",
        "game.anonymous": "Player",

        "game.over_title": "Time!",
        "game.final_detail": "{name} · {coins} rings in {seconds} seconds",
        "game.finished_at": "Finished at {time}",
        "game.fullscreen_hint": "Try Again keeps you in fullscreen · Esc leaves it",
        "game.rank": "Position {rank} of {total}",
        "game.rank_first": "🥇 New best score!",
        "game.podium": "Top scores",
        "game.try_again": "🔄 Try Again",
        "game.finish": "Finish — next player",
        "game.back": "⬅ Back",

        "game.leaderboard_title": "Leaderboard",
        "game.leaderboard_subtitle":
            "Every run recorded on this computer, best first.",
        "game.board_empty": "No runs yet. Be the first.",
        "game.your_position": "You: position {rank} of {total} · {score} points",
        "game.coins_short": "{coins} rings",

        "log.run_started": "Ring run started for {name} ({seconds}s).",
        "log.run_finished": "Ring run finished: {name} scored {score}.",
        "log.run_abandoned": "Ring run abandoned — left the test screen.",
        "log.session_handoff": "Session finished. Ready for the next player.",

        # ── Trained action names ─────────────────────────────────────────────
        "action.neutral": "Neutral",
        "action.push": "Push",
        "action.pull": "Pull",
        "action.lift": "Lift",
        "action.drop": "Drop",
        "action.left": "Left",
        "action.right": "Right",
        "action.rotateLeft": "Rotate left",
        "action.rotateRight": "Rotate right",
        "action.disappear": "Disappear",

        # ── Brain map ────────────────────────────────────────────────────────
        "brainmap.title": "Training Result",
        "brainmap.subtitle":
            "Each dot is one trained action. The further apart they are, the more "
            "reliably the headset can tell them apart.",
        "brainmap.empty": "No brain map data yet.",
        "brainmap.loading": "Reading the brain map from Cortex…",
        "brainmap.axis_x": "Distinctness ←→",
        "brainmap.axis_y": "Distance from neutral",
        "brainmap.separation": "Closest pair: {gap}",
        "brainmap.quality.good": "Well separated — good training",
        "brainmap.quality.fair": "Usable, but two actions sit close together",
        "brainmap.quality.poor": "Actions overlap — retraining is worth it",
        "brainmap.quality.unknown": "Not enough trained actions to compare",
        "brainmap.hint.good": "You are ready to fly. Continue to the test controls.",
        "brainmap.hint.fair":
            "It will work, but expect the occasional wrong command. "
            "Retraining usually pulls the dots apart.",
        "brainmap.hint.poor":
            "Cortex is confusing these actions. Retrain and try to hold a more "
            "distinct, consistent thought for each one.",
        "brainmap.retrain": "🔄 Train Again",
        "brainmap.continue": "Continue to Test Controls ➔",
        "brainmap.refresh": "Refresh",

        # ── Settings dialog ──────────────────────────────────────────────────
        "settings.title": "⚙ Configurations",
        "settings.motion": "🎯 Motion Settings",
        "settings.invert_yaw": "Invert Head Left/Right (Yaw)",
        "settings.sens_left": "Left Sens.",
        "settings.sens_left.tip": "Multiplies intensity when turning your head left (Yaw).",
        "settings.sens_right": "Right Sens.",
        "settings.sens_right.tip": "Multiplies intensity when turning your head right (Yaw).",
        "settings.sens_fwd": "Fwd Sens.",
        "settings.sens_fwd.tip": (
            "Multiplies intensity when tilting your head down (Pitch Forward)."
        ),
        "settings.sens_back": "Back Sens.",
        "settings.sens_back.tip": (
            "Multiplies intensity when tilting your head up (Pitch Backward)."
        ),
        "settings.deadzone": "Deadzone",
        "settings.deadzone.tip": (
            "Creates an 'ignore bubble' around the center. "
            "Increase to ignore unintentional tiny wobbles."
        ),
        "settings.smoothing": "Smoothing",
        "settings.smoothing.tip": (
            "Averages movements. Higher = smoother flight but adds a slight delay. "
            "Lower = more twitchy."
        ),
        "settings.max_speed": "Max Speed",
        "settings.max_speed.tip": (
            "A hard safety limit (0-100) on how fast the drone is allowed to fly."
        ),
        "settings.emotiv": "🧠 Emotiv API Settings",
        "settings.loading": "Loading data from headset...",
        "settings.not_connected": "Headset not connected.",
        "settings.threshold": "Current Threshold: {threshold} | Last Score: {score}",
        "settings.action_sens": "{action} Sens.",
        "settings.mental": "🧠 Mental Commands",
        "settings.none": "None",
        "settings.close": "Close",
        "settings.language": "Language",
        "settings.restart_hint": "Applies immediately.",

        # ── Log lines emitted by the UI itself ───────────────────────────────
        "log.no_headsets": (
            "No headsets found. Make sure Emotiv App is running and headset is turned on."
        ),
        "log.headset_gone": "{headset} is no longer available. Pick another headset.",
        "log.headsets_available": "{count} headset(s) available. Please select one to connect.",
        "log.no_headset_selected": "No valid headset selected.",
        "log.connecting_headset": "Connecting to headset '{headset}'...",
        "log.client_not_init": "Error: Drone client not initialized.",
        "log.profiles_available": "{count} profile(s) available. Please select one to load.",
        "log.no_profile_selected": "No valid profile selected.",
        "log.loading_profile": "Loading profile '{profile}'...",
        "log.bci_not_connected": "Error: BCI not connected. Connect first, then load a profile.",
        "log.refreshing_profiles": "Refreshing profile list...",
        "log.refresh_failed": "Refresh failed: {detail}",
        "log.releasing_headset": "Disconnecting the headset and re-scanning…",
        "log.switching_headset": "Disconnecting {headset} before switching…",
        "reconnect.title": "⚠️ Headset disconnected",
        "reconnect.detail": "Lost contact with {headset}. Put the headset back on and keep it near the receiver — reconnecting automatically.",
        "reconnect.remaining": "Giving up in {seconds}s",
        "log.headset_lost": "Lost {headset}. Trying to reconnect…",
        "log.headset_recovered": "{headset} is back. Resuming.",
        "log.headset_lost_final": "Gave up on {headset}. Returning to the headset list.",
        "log.sensor_labels": "Headset sensors: {labels}",
        "log.bci_status": "BCI Status: {status}",
        "log.retry_access": "Retrying requestAccess with EMOTIV Cortex...",
        "log.retry_failed": "Retry failed: {detail}",
        "log.enter_profile_name": "Please enter a new profile name.",
        "log.recenter": "Manual recenter triggered.",
        "log.brainmap_ready": "Brain map received — {quality}",
        "log.training_rejected": "Take discarded for '{action}' — recording again.",
        "log.disconnecting": "Disconnecting...",
        "log.disconnected": "Disconnected and returned to setup.",
        "log.hud_opened": "Opened Fullscreen HUD.",
        "log.hud_closed": "Closed Fullscreen HUD.",
        "log.sim_takeoff": "[SIM] Virtual takeoff",
        "log.sim_landing": "[SIM] Virtual landing",
        "log.sim_emergency": "[SIM] Emergency stop",
        "log.airborne": "Airborne! Head tracking active.",
        "log.takeoff_failed": "Takeoff failed: {detail}",
        "log.landed": "Landed safely",
        "log.motors_stopped": "Motors stopped",
        "log.error": "Error: {detail}",
        "log.camera_started": "Camera stream started",
        "log.camera_error": "Camera error: {detail}",
        "log.pyav_active": "PyAV direct decode active (color-corrected)",
        "log.pyav_failed": "PyAV direct open failed, using fallback: {detail}",

        # ── Status strings that arrive from the Cortex layer ─────────────────
        "bstatus.connecting_cortex": "Connecting to Emotiv Cortex...",
        "bstatus.session_created": "Session Created (waiting for streams...)",
        "bstatus.session_active": "Session Active",
        "bstatus.simulation_active": "Simulation Active",
        "bstatus.recenter": "Headset center reset requested",
        "bstatus.headset_connected": "Headset connected (warning code 104)",
        "bstatus.scan_finished": "Headset scanning finished (warning code 142)",
        "bstatus.connecting_headset": "Connecting to headset '{headset}'...",
        "bstatus.loading_profile": "Loading profile '{profile}'...",
        "bstatus.profile_load_error": "Profile load error: {detail}",
        "bstatus.cortex_error": "Cortex error: {detail}",
        "bstatus.profile_loaded": "Profile '{profile}' loaded. Ready for flight!",
    },

    "zh": {
        "lang.name": "中文",

        # ── Shell ────────────────────────────────────────────────────────────
        "app.title": "Tello 脑机接口控制器",
        "btn.settings": "⚙ 设置",
        "header.language": "🌐 语言",

        # ── Step 1 · authentication ──────────────────────────────────────────
        "auth.title": "连接出现问题",
        "auth.intro":
            "应用无法连接到 EMOTIV Cortex。请依次检查以下项目 —— "
            "只有在技术支持要求更改时，才需要修改下方的凭据。",
        "auth.check_launcher":
            "1. EMOTIV Launcher 是否已运行并已登录？请先启动它，然后点击“重新连接”。",
        "auth.check_approved":
            "2. 本应用是否已获批准？EMOTIV Launcher 首次会弹出授权提示 —— "
            "请批准后点击“重新连接”。",
        "auth.reason": "报告的问题：{detail}",
        "auth.group": "凭据（通常不是问题所在）",
        "auth.checks_group": "请先检查以下项目",
        "auth.client_id": "Client ID：",
        "auth.client_secret": "Client Secret：",
        "auth.simulate": "模拟模式（无需头戴设备即可测试界面）",
        "auth.auto_connect": "启动时自动连接",
        "auth.auto_connect.tip": "保存 Client ID 与 Secret 后，打开应用即跳过本页面并直接开始连接。",
        "auth.connect": "授权",
        "auth.retry": "重新连接",
        "auth.retrying": "正在重新连接…",
        "auth.logs": "脑机接口连接日志：",
        "auth.log_file": "完整日志文件：{path}",

        # ── Step 2 · headset ─────────────────────────────────────────────────
        "headset.title": "第 1 步：选择头戴设备",
        "headset.tagline": "用意念驾驶无人机。请选择您正在佩戴的头戴设备以开始。",
        "headset.group": "可用的头戴设备",
        "headset.awaiting_auth": "— 等待授权 —",
        "headset.connect": "连接头戴设备",
        "headset.connecting_btn": "⏳ 连接中…",
        "headset.none_found": "⚠️ 未找到头戴设备",
        "headset.count": "找到 {count} 台",
        "hstatus.discovered": "可连接",
        "hstatus.connected": "已连接",
        "hstatus.connecting": "正在连接…",
        "hstatus.discovering": "正在搜索…",
        "headset.back": "⬅ 返回授权",

        # ── Live tuning on the simulator screen ──────────────────────────────
        "tune.mental": "意念指令",
        "tune.mental_waiting": "加载一个已训练的配置文件，即可调整各指令的触发难度。",

        "retrain.button": "♻ 重置并重新训练",
        "retrain.tip": "清除此配置文件的训练数据并重新训练一遍",
        "retrain.title": "要重置训练数据吗？",
        "retrain.body": "「{profile}」中所有已训练的动作都会被清除，包括中性基线，并将从信号检查开始重新训练。配置文件本身会保留。",
        "retrain.confirm": "清除并重新训练",

        "common.cancel": "取消",

        "log.mc_sensitivity": "意念指令灵敏度已设置为 {values}。",
        "log.no_profile_to_retrain": "请先加载一个已训练的配置文件再重新训练。",

        "headset.refresh": "🔄 刷新",
        "headset.refresh.tip": "重新扫描头戴设备并从 Cortex 重新获取列表",
        "headset.refreshing": "⏳ 扫描中…",

        "profile.deleted": "配置文件「{profile}」已删除。",
        "profile.reset_done": "「{profile}」的训练数据已清除。",

        "log.auto_connecting": "找到已保存的凭据 — 正在自动连接。",
        "log.refreshing_headsets": "正在重新扫描头戴设备…",
        "log.profile_deleting": "正在删除配置文件「{profile}」…",
        "log.profile_deleted": "配置文件「{profile}」已删除。",
        "log.profile_resetting": "正在清除「{profile}」的训练数据…",
        "log.profile_reset": "「{profile}」的训练数据已清除。",

        "badge.bci_active": "🟢 脑机接口：已激活",
        "badge.profile_loaded": "🟢 🧠 配置文件「{profile}」已加载，可以起飞了！",

        # ── Step 3 · profile ─────────────────────────────────────────────────
        "profile.title": "第 2 步：训练配置文件",
        "profile.group": "训练配置文件",
        "profile.label": "配置文件：",
        "profile.refresh": "🔄 刷新",
        "profile.refresh.tip": "重新从 Cortex 获取配置文件列表",
        "profile.connect_first": "— 请先连接头戴设备 —",
        "profile.load": "🧠 加载所选配置文件",
        "profile.loading_btn": "⏳ 加载中…",
        "profile.hint": "用你的名字创建一个配置文件，然后开始训练。",
        "profile.create_label": "输入你的名字并开始训练：",
        "profile.new_placeholder": "你的名字…",
        "profile.create_train": "🧠 新建并训练",
        "profile.none_found": "⚠️ 未找到配置文件",
        "profile.none_hint": "未找到训练配置文件。请在 EMOTIV Launcher 中创建一个。",
        "profile.available": "共有 {count} 个配置文件 — 选择一个并点击「加载」。",
        "profile.selected": "已选择配置文件「{profile}」，准备就绪。",
        "profile.session_active": "会话已激活。请选择一个配置文件并点击「加载」。",
        "profile.back": "⬅ 返回头戴设备",
        "profile.next": "下一步：测试控制 ➔",

        # ── EMOTIV Launcher approval banner ──────────────────────────────────
        "access.title": "需要 EMOTIV Launcher 授权",
        "access.steps": (
            "1. 在电脑上打开 <b>EMOTIV Launcher</b>。\n"
            "2. 查找本应用发出的权限请求通知。\n"
            "3. 点击<b>允许</b>以授予访问权限。\n"
            "4. 然后点击下方的<b>重试</b>。"
        ),
        "access.retry": "🔄 已授权 — 重试",
        "access.rejected_title": "访问被拒绝",
        "access.rejected_body":
            "本应用在 EMOTIV Launcher 中被拒绝，因此无法读取头戴设备。"
            "请打开 EMOTIV Launcher 批准本应用，然后点击“重试”。",
        "access.waiting": "正在等待 EMOTIV Launcher 中的授权…",
        "access.checking": "正在检查本应用是否已获批准…",
        "access.granted": "已通过 EMOTIV Launcher 批准。",
        "access.default_msg": "尚未获得访问权限。请打开 EMOTIV Launcher 并批准本应用。",

        # ── EEG quality check ────────────────────────────────────────────────
        "eq.title": "脑电信号质量检查",
        "eq.subtitle": "开始训练前，请确认所有电极的接触质量良好。",
        "eq.overall_waiting": "整体信号：等待中…",
        "eq.overall": "传感器接触：{quality}（{value}%）",
        "quality.unknown_state": "等待中…",
        "eq.group": "电极接触质量",
        "eq.waiting_data": "等待传感器数据…",
        "eq.ok": "✅ 信号质量已满足训练要求。",
        "dash.battery": "无人机电量：{value}%",
        "dash.battery_empty": "无人机电量：—",
        "dash.camera": "📹 实时摄像画面",
        "dash.controls": "🕹️ 飞行与控制",
        "dash.disconnect": "🔌 断开并退出",
        "dash.drone_connected": "🟢 无人机：已连接",
        "dash.drone_sim": "🟡 无人机：模拟中",
        "dash.emergency": "⛔ 紧急停止",
        "dash.headset": "头戴设备：{battery}% | 信号：{signal}/4",
        "dash.headset_empty": "头戴设备：—",
        "dash.height": "高度：{value} 厘米",
        "dash.height_empty": "高度：—",
        "dash.hud": "📺 全屏 HUD",
        "dash.land": "🛬 降落",
        "dash.log": "📟 日志",
        "dash.mc": "🧠 意念指令：{action}",
        "dash.mc_none": "🧠 意念指令：无",
        "dash.recenter": "🎯 重新校准",
        "dash.system": "系统",
        "dash.takeoff": "🚀 起飞",
        "dash.telemetry": "📊 遥测数据",
        "dash.temp": "温度：{value}°C",
        "dash.temp_empty": "温度：—",
        "drone.back": "⬅ 返回测试",
        "drone.connect": "连接无人机",
        "drone.connected": "无人机连接成功！电量：{battery}%",
        "drone.connecting": "正在连接 Tello WiFi…",
        "drone.failed": "连接失败：{detail}",
        "drone.launch": "启动飞行仪表盘 🚀",
        "drone.ready": "准备连接。",
        "drone.sim_skip": "模拟模式，跳过真实无人机连接。",
        "drone.subtitle": "继续之前，请确认电脑已连接到无人机的 WiFi 网络。",
        "drone.title": "第 4 步：连接 DJI Tello",
        "eq.back": "⬅ 返回配置文件",
        "eq.bad": "⚠️ 请先改善电极接触，调整头戴设备后再训练。",
        "eq.next": "开始训练 ➔",
        "quality.bad": "差",
        "quality.fair": "一般",
        "quality.good": "良好",
        "quality.none": "无信号",
        "quality.poor": "较差",
        "quality.short_unknown": "？",
        "quality.unknown": "未知（{value}）",
        "quality.very_bad": "非常差",
        "sim.altitude": "高度 {alt} 米",
        "sim.esc_hint": "按 ESC 退出全屏",
        "sim.mental_command": "🧠 {action}",
        "sim.readout": "高度 {alt} 米   ·   速度 {spd}",
        "sim.score": "🏆 {score}",
        "test.back": "⬅ 返回",
        "test.next": "下一步：连接真实无人机 ➔",
        "test.recenter": "🎯 重新校准头戴设备",
        "test.state_group": "模拟器",
        "test.title": "第 3 步：飞行模拟器",
        "train.accept": "接受",
        "train.accepting": "正在接受训练结果…",
        "train.complete": "全部训练完成！正在保存配置文件…",
        "train.failed": "训练失败！数据质量不佳。",
        "train.finish": "完成并前往测试控制",
        "train.abandon": "⬅ 重新开始 —— 返回设备列表",
        "train.abandon.tip": "停止本次训练并释放头戴设备，交给下一位使用者。",
        "log.training_abandoned": "训练已放弃，正在释放头戴设备。",
        "train.finishing": "正在收尾…",
        "train.get_ready": "准备…",
        "train.neutral.subtitle": "请放松并保持头脑清空。无人机应保持静止。",
        "train.neutral.title": "训练：中性基线",
        "train.push.subtitle": "注视无人机，用意念想象把它向前推。",
        "train.push.title": "训练：推（前进）指令",
        "train.recording": "记录中…剩余 {seconds} 秒",
        "train.reject": "拒绝（重试）",
        "train.retry": "重试",
        "train.retrying": "正在重新训练…",
        "train.succeeded": "训练成功！数据质量良好。",
        "train.waiting": "等待训练开始…",
        "droneaction.FlipRight": "右翻",
        "droneaction.MoveBack": "后退",
        "droneaction.MoveDown": "下降",
        "droneaction.MoveForward": "前进",
        "droneaction.MoveLeft": "向左",
        "droneaction.MoveRight": "向右",
        "droneaction.MoveUp": "上升",

        # ── 如何飞行 ───────────────────────────────────────────────────
        "howto.recenter": "坐好了吗？按“重新居中”将当前头部位置设为新的正前方。",
        "howto.overlay_steer": "转动头部控制方向",
        "howto.overlay_forward": "意念“{action}”即可前进",
        "howto.overlay_rings": "穿过光环 —— 每个 10 分",

        # ── 结果祝贺 ───────────────────────────────────────────────────
        "game.congrats_first": "🥇 恭喜 —— 您获得了第 1 名！",
        "game.congrats_podium": "🎉 恭喜 —— 您登上了领奖台，第 {rank} 名！",
        "game.congrats_ranked": "飞得不错 —— 您在 {total} 人中排第 {rank} 名！",
        "game.congrats_only": "🥇 恭喜 —— 您创下了第一个成绩！",
        "game.mind_message": "而这一切，完全靠您的意念完成。🧠",
        "game.ordinal_1": "1", "game.ordinal_2": "2", "game.ordinal_3": "3",
        "game.ordinal_n": "{n}",

        # ── 电极接触质量头部图 ─────────────────────────────────────
        "eq.headmap_group": "传感器位置（10–20 系统）",
        "eq.headmap_hint":
            "每个圆点代表一个传感器，按它在头部的实际位置绘制 —— 鼻子在上方。"
            "绿色表示接触良好，红色表示需要调整。",
        "eq.headmap_front": "前",
        "eq.headmap_back": "后",
        "eq.headmap_waiting": "等待头戴设备…",
        "eq.legend": "接触：",
        "hud.no_signal": "无摄像信号",
        "hud.esc": "按 ESC 退出",

        "cue.neutral": "放松 — 让无人机悬停",
        "cue.push": "用意念把无人机向前推",

        # ── Ring run / leaderboard ───────────────────────────────────────────
        "game.group": "🏁 冲环挑战 — {seconds} 秒",
        "game.name_placeholder": "你的名字",
        "game.playing_as": "当前玩家",
        "game.no_profile": "— 请先训练一个配置文件 —",
        "game.start": "▶ 开始挑战",
        "game.running": "挑战进行中…",
        "game.get_ready": "准备好！",
        "game.go": "开始！",
        "game.show_leaderboard": "🏆 查看排行榜",
        "game.timer": "{seconds} 秒",
        "game.idle_hint": "点击「开始挑战」进入计时回合",
        "game.anonymous": "玩家",

        "game.over_title": "时间到！",
        "game.final_detail": "{name} · {seconds} 秒内收集 {coins} 个圆环",
        "game.finished_at": "结束于 {time}",
        "game.fullscreen_hint": "「再来一次」会保持全屏 · 按 Esc 退出全屏",
        "game.rank": "第 {rank} 名，共 {total} 名",
        "game.rank_first": "🥇 新的最高分！",
        "game.podium": "最高分",
        "game.try_again": "🔄 再来一次",
        "game.finish": "结束 — 换下一位玩家",
        "game.back": "⬅ 返回",

        "game.leaderboard_title": "排行榜",
        "game.leaderboard_subtitle": "本机记录的所有成绩，从高到低排列。",
        "game.board_empty": "还没有成绩，来做第一个吧。",
        "game.your_position": "你：第 {rank} 名，共 {total} 名 · {score} 分",
        "game.coins_short": "{coins} 个环",

        "log.run_started": "{name} 的冲环挑战已开始（{seconds} 秒）。",
        "log.run_finished": "冲环挑战结束：{name} 得分 {score}。",
        "log.run_abandoned": "冲环挑战已放弃 — 离开了测试页面。",
        "log.session_handoff": "本次体验结束，可以换下一位玩家了。",

        # ── Trained action names ─────────────────────────────────────────────
        "action.neutral": "中性",
        "action.push": "推",
        "action.pull": "拉",
        "action.lift": "上升",
        "action.drop": "下降",
        "action.left": "向左",
        "action.right": "向右",
        "action.rotateLeft": "向左旋转",
        "action.rotateRight": "向右旋转",
        "action.disappear": "消失",

        # ── Brain map ────────────────────────────────────────────────────────
        "brainmap.title": "训练结果",
        "brainmap.subtitle": "每个圆点代表一个已训练的动作。点之间距离越远，设备就越能可靠地区分它们。",
        "brainmap.empty": "暂无脑图数据。",
        "brainmap.loading": "正在从 Cortex 读取脑图…",
        "brainmap.axis_x": "区分度 ←→",
        "brainmap.axis_y": "与中性状态的距离",
        "brainmap.separation": "最接近的一对：{gap}",
        "brainmap.quality.good": "区分良好 — 训练效果不错",
        "brainmap.quality.fair": "可以使用，但有两个动作靠得较近",
        "brainmap.quality.poor": "动作相互重叠 — 建议重新训练",
        "brainmap.quality.unknown": "已训练的动作太少，无法比较",
        "brainmap.hint.good": "可以开始飞行了，继续前往测试控制。",
        "brainmap.hint.fair": "能用，但偶尔会识别错。重新训练通常能把这些点拉开。",
        "brainmap.hint.poor": "Cortex 正在混淆这些动作。请重新训练，每个动作尽量保持更清晰、更稳定的意念。",
        "brainmap.retrain": "🔄 重新训练",
        "brainmap.continue": "继续前往测试控制 ➔",
        "brainmap.refresh": "刷新",

        # ── Settings dialog ──────────────────────────────────────────────────
        "settings.title": "⚙ 设置",
        "settings.motion": "🎯 动作设置",
        "settings.invert_yaw": "反转头部左右（偏航）",
        "settings.sens_left": "左转灵敏度",
        "settings.sens_left.tip": "头部向左转（偏航）时的强度倍数。",
        "settings.sens_right": "右转灵敏度",
        "settings.sens_right.tip": "头部向右转（偏航）时的强度倍数。",
        "settings.sens_fwd": "前倾灵敏度",
        "settings.sens_fwd.tip": "头部向下低头（前俯）时的强度倍数。",
        "settings.sens_back": "后仰灵敏度",
        "settings.sens_back.tip": "头部向上抬头（后仰）时的强度倍数。",
        "settings.deadzone": "死区",
        "settings.deadzone.tip": "在中心位置周围建立一个「忽略区」。数值越大，越会忽略无意的细微晃动。",
        "settings.smoothing": "平滑度",
        "settings.smoothing.tip": "对动作取平均值。数值越大飞行越平稳，但会有轻微延迟；越小则越灵敏跳动。",
        "settings.max_speed": "最大速度",
        "settings.max_speed.tip": "无人机飞行速度的硬性安全上限（0-100）。",
        "settings.emotiv": "🧠 Emotiv API 设置",
        "settings.loading": "正在从头戴设备读取数据…",
        "settings.not_connected": "头戴设备未连接。",
        "settings.threshold": "当前阈值：{threshold} | 上次得分：{score}",
        "settings.action_sens": "{action} 灵敏度",
        "settings.mental": "🧠 意念指令",
        "settings.none": "无",
        "settings.close": "关闭",
        "settings.language": "语言",
        "settings.restart_hint": "立即生效。",

        # ── Log lines emitted by the UI itself ───────────────────────────────
        "log.no_headsets": "未找到头戴设备。请确认 Emotiv 应用正在运行且设备已开机。",
        "log.headset_gone": "{headset} 已不可用。请选择其他头戴设备。",
        "log.headsets_available": "共有 {count} 台头戴设备可用，请选择一台进行连接。",
        "log.no_headset_selected": "未选择有效的头戴设备。",
        "log.connecting_headset": "正在连接头戴设备「{headset}」…",
        "log.client_not_init": "错误：无人机客户端尚未初始化。",
        "log.profiles_available": "共有 {count} 个配置文件可用，请选择一个进行加载。",
        "log.no_profile_selected": "未选择有效的配置文件。",
        "log.loading_profile": "正在加载配置文件「{profile}」…",
        "log.bci_not_connected": "错误：脑机接口未连接。请先连接，再加载配置文件。",
        "log.refreshing_profiles": "正在刷新配置文件列表…",
        "log.refresh_failed": "刷新失败：{detail}",
        "log.releasing_headset": "正在断开头戴设备并重新扫描…",
        "log.switching_headset": "正在断开 {headset} 以切换设备…",
        "reconnect.title": "⚠️ 头戴设备已断开",
        "reconnect.detail": "与 {headset} 失去连接。请重新戴好设备并靠近接收器 —— 正在自动重连。",
        "reconnect.remaining": "{seconds} 秒后放弃",
        "log.headset_lost": "已失去 {headset} 的连接，正在尝试重连…",
        "log.headset_recovered": "{headset} 已恢复连接，继续。",
        "log.headset_lost_final": "已放弃 {headset}，返回设备列表。",
        "log.sensor_labels": "头戴设备传感器：{labels}",
        "log.bci_status": "脑机接口状态：{status}",
        "log.retry_access": "正在向 EMOTIV Cortex 重新发送授权请求…",
        "log.retry_failed": "重试失败：{detail}",
        "log.enter_profile_name": "请输入新的配置文件名称。",
        "log.recenter": "已手动触发重新校准。",
        "log.brainmap_ready": "已获取脑图 — {quality}",
        "log.training_rejected": "已丢弃「{action}」的这次采集 — 正在重新记录。",
        "log.disconnecting": "正在断开连接…",
        "log.disconnected": "已断开连接并返回设置页面。",
        "log.hud_opened": "已打开全屏 HUD。",
        "log.hud_closed": "已关闭全屏 HUD。",
        "log.sim_takeoff": "[模拟] 虚拟起飞",
        "log.sim_landing": "[模拟] 虚拟降落",
        "log.sim_emergency": "[模拟] 紧急停止",
        "log.airborne": "已升空！头部追踪已启用。",
        "log.takeoff_failed": "起飞失败：{detail}",
        "log.landed": "已安全降落",
        "log.motors_stopped": "电机已停止",
        "log.error": "错误：{detail}",
        "log.camera_started": "摄像画面已启动",
        "log.camera_error": "摄像出错：{detail}",
        "log.pyav_active": "PyAV 直接解码已启用（颜色已校正）",
        "log.pyav_failed": "PyAV 直接打开失败，改用备用方式：{detail}",

        # ── Status strings that arrive from the Cortex layer ─────────────────
        "bstatus.connecting_cortex": "正在连接 Emotiv Cortex…",
        "bstatus.session_created": "会话已创建（等待数据流…）",
        "bstatus.session_active": "会话已激活",
        "bstatus.simulation_active": "模拟模式已激活",
        "bstatus.recenter": "已请求重新校准头戴设备中心",
        "bstatus.headset_connected": "头戴设备已连接（警告代码 104）",
        "bstatus.scan_finished": "头戴设备扫描结束（警告代码 142）",
        "bstatus.connecting_headset": "正在连接头戴设备「{headset}」…",
        "bstatus.loading_profile": "正在加载配置文件「{profile}」…",
        "bstatus.profile_load_error": "配置文件加载错误：{detail}",
        "bstatus.cortex_error": "Cortex 错误：{detail}",
        "bstatus.profile_loaded": "配置文件「{profile}」已加载，可以起飞了！",
    },
}

LANGUAGES = [("en", "English"), ("zh", "中文")]

_LANG = "en"
_PLACEHOLDER = re.compile(r"\{[a-zA-Z_]+\}")


def available_languages():
    return list(LANGUAGES)


def get_lang() -> str:
    return _LANG


def set_lang(lang: str) -> str:
    """Switch the active language. Unknown codes fall back to English."""
    global _LANG
    _LANG = lang if lang in I18N else "en"
    return _LANG


def has(key: str) -> bool:
    """True when `key` exists in any table — lets callers fall back to raw text."""
    return key in I18N["en"] or key in I18N.get(_LANG, {})


def t(key: str, **params) -> str:
    """Look up `key` in the active language, falling back to English."""
    text = I18N.get(_LANG, {}).get(key)
    if text is None:
        text = I18N["en"].get(key)
    if text is None:
        return key
    if params:
        for name, value in params.items():
            text = text.replace("{" + name + "}", "" if value is None else str(value))
    # Never leak an unfilled "{detail}" onto the screen.
    return _PLACEHOLDER.sub("", text).strip()


# ── Runtime re-translation ───────────────────────────────────────────────────
#
# bind() records which key produced a widget's text so retranslate() can redo it
# after the language changes. The spec lives on the widget itself, so calling
# bind() again on the same widget (a status label updating at 20 Hz, say) just
# overwrites it instead of growing the registry.

_REGISTRY = []


def _needs_mnemonic_escape(widget, setter: str) -> bool:
    """Whether this widget will read '&' as a keyboard accelerator.

    Buttons, checkboxes and group-box titles do; plain labels do not. Detected by
    duck typing so this module stays free of any Qt import: QAbstractButton has
    setShortcut, QGroupBox has setTitle plus setCheckable.
    """
    if setter == "setTitle":
        return True
    if setter != "setText":
        return False
    return hasattr(widget, "setShortcut")


def _apply(widget, setter: str, text: str):
    # "Reset & Retrain" would otherwise render as "Reset _Retrain" with R
    # underlined. Doing it here means translators never have to know.
    if "&" in text and _needs_mnemonic_escape(widget, setter):
        text = text.replace("&", "&&")
    getattr(widget, setter)(text)


def bind(widget, key: str, setter: str = "setText", **params):
    """Set `widget`'s text from `key` and remember how, for later retranslation.

    Keyed by setter, so a widget can carry a label and a tooltip at once.
    """
    if not hasattr(widget, "_i18n_spec"):
        widget._i18n_spec = {}
        _REGISTRY.append(widget)
    widget._i18n_spec[setter] = (key, params)
    _apply(widget, setter, t(key, **params))
    return widget


def unbind(widget):
    """Forget a widget — used for dialogs that are rebuilt on every open."""
    if hasattr(widget, "_i18n_spec"):
        del widget._i18n_spec
        try:
            _REGISTRY.remove(widget)
        except ValueError:
            pass


def retranslate():
    """Re-apply every bound key. Widgets whose C++ side is gone are dropped."""
    for widget in list(_REGISTRY):
        try:
            for setter, (key, params) in widget._i18n_spec.items():
                _apply(widget, setter, t(key, **params))
        except RuntimeError:
            # Underlying Qt object was deleted.
            _REGISTRY.remove(widget)


# ── Cortex-layer status strings ──────────────────────────────────────────────
#
# drone_controller/cortex still talk in finished English sentences. Rather than
# reshape that protocol, translate at the boundary: known sentences map to keys,
# anything unrecognised passes through in English.

_BACKEND_EXACT = {
    "Connecting to Emotiv Cortex...": "bstatus.connecting_cortex",
    "Session Created (waiting for streams...)": "bstatus.session_created",
    "Session Active": "bstatus.session_active",
    "Simulation Active": "bstatus.simulation_active",
    "Headset center reset requested": "bstatus.recenter",
    "Headset connected (warning code 104)": "bstatus.headset_connected",
    "Headset scanning finished (warning code 142)": "bstatus.scan_finished",
}

_BACKEND_PATTERNS = [
    (re.compile(r"^Connecting to headset '(.*)'\.\.\.$"),
     "bstatus.connecting_headset", ("headset",)),
    (re.compile(r"^Loading profile '(.*)'\.\.\.$"),
     "bstatus.loading_profile", ("profile",)),
    (re.compile(r"^Profile load error: (.*)$"),
     "bstatus.profile_load_error", ("detail",)),
    (re.compile(r"^Cortex error: (.*)$"),
     "bstatus.cortex_error", ("detail",)),
    (re.compile(r"^Profile '(.*)' loaded\. Ready for flight!$"),
     "bstatus.profile_loaded", ("profile",)),
]


def headset_status(status: str) -> str:
    """Cortex's headset state word, in the user's language.

    Cortex reports these in English ("discovered", "connected"); unknown states
    pass through untouched rather than vanishing.
    """
    key = f"hstatus.{str(status).lower()}"
    return t(key) if has(key) else str(status)


def drone_action(action: str) -> str:
    """Player-facing name for a drone action.

    The adapter and the config file talk in English CamelCase identifiers
    ("MoveForward"), which is right for a protocol and wrong for a banner shown
    mid-game. Unknown actions fall through unchanged rather than blanking out.
    """
    if not action:
        return ""
    key = f"droneaction.{action}"
    return t(key) if has(key) else action


def ordinal(n: int) -> str:
    """'1st', '2nd', '3rd', '4th' — and whatever the language uses instead."""
    key = f"game.ordinal_{n}" if n in (1, 2, 3) else "game.ordinal_n"
    return t(key, n=n)


def backend_status(text: str) -> str:
    """Translate a status sentence produced by the Cortex layer."""
    key = _BACKEND_EXACT.get(text)
    if key:
        return t(key)
    for pattern, key, names in _BACKEND_PATTERNS:
        match = pattern.match(text)
        if match:
            return t(key, **dict(zip(names, match.groups())))
    return text


def profile_name_from_loaded(text: str) -> str:
    """Pull the profile name out of the backend's PROFILE_LOADED message."""
    match = re.match(r"^Profile '(.*)' loaded\.", text)
    return match.group(1) if match else ""
