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
        "auth.title": "Step 1: Authenticate with Cortex",
        "auth.group": "Credentials",
        "auth.client_id": "Client ID:",
        "auth.client_secret": "Client Secret:",
        "auth.simulate": "Simulation Mode (Test UI without headset)",
        "auth.connect": "Authenticate",
        "auth.retry": "Retry Connection",
        "auth.logs": "BCI Connection Logs:",

        # ── Step 2 · headset ─────────────────────────────────────────────────
        "headset.title": "Step 2: Select Headset",
        "headset.group": "Available Headsets",
        "headset.awaiting_auth": "— awaiting authentication —",
        "headset.connect": "Connect Headset",
        "headset.connecting_btn": "⏳ Connecting...",
        "headset.none_found": "⚠️ No headsets found",
        "headset.item": "🎧 {id} ({status})",
        "headset.back": "⬅ Back to Auth",

        "badge.not_connected": "🔴 Not Connected",
        "badge.connecting": "🟡 Connecting...",
        "badge.waiting_approval": "🟡 Waiting for EMOTIV Launcher approval...",
        "badge.bci_active": "🟢 BCI: Active",
        "badge.scan_finished": "🔴 BCI: Scan Finished / Not Found",
        "badge.profile_loaded": "🟢 🧠 Profile '{profile}' loaded. Ready for flight!",
        "badge.status": "🟡 {status}",

        # ── Step 3 · profile ─────────────────────────────────────────────────
        "profile.title": "Step 3: Training Profile",
        "profile.group": "Available Profiles",
        "profile.label": "Profile:",
        "profile.refresh": "🔄 Refresh",
        "profile.refresh.tip": "Re-fetch profile list from Cortex",
        "profile.connect_first": "— connect headset first —",
        "profile.load": "🧠 Load Selected Profile",
        "profile.loading_btn": "⏳ Loading...",
        "profile.hint": "Select a training profile after connecting.",
        "profile.new_placeholder": "New Profile Name...",
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
        "access.default_msg": (
            "Access not granted. Please open EMOTIV Launcher and approve this application."
        ),

        # ── EEG quality check ────────────────────────────────────────────────
        "eq.title": "EEG Signal Quality Check",
        "eq.subtitle": "Ensure all sensors show good contact quality before training.",
        "eq.overall_waiting": "Overall Signal: Waiting...",
        "eq.overall": "Overall Signal: {quality} ({value}/4)",
        "eq.group": "Sensor Contact Quality",
        "eq.waiting_data": "Waiting for sensor data...",
        "eq.ok": "✅ Signal quality is sufficient for training.",
        "eq.bad": "⚠️ Improve sensor contact before training. Adjust the headset.",
        "eq.back": "⬅ Back to Profiles",
        "eq.next": "Start Training ➔",

        "quality.none": "No Signal",
        "quality.very_bad": "Very Bad",
        "quality.bad": "Bad",
        "quality.poor": "Poor",
        "quality.fair": "Fair",
        "quality.good": "Good",
        "quality.unknown": "Unknown ({value})",
        "quality.short_unknown": "?",

        # ── Training screens ─────────────────────────────────────────────────
        "train.neutral.title": "Training: Neutral Baseline",
        "train.neutral.subtitle": "Relax and keep your mind clear. The drone should stay still.",
        "train.push.title": "Training: Push Command (Forward)",
        "train.push.subtitle": "Focus on the drone. Imagine pushing it forward with your mind.",
        "train.waiting": "Waiting for training to start...",
        "train.get_ready": "Get ready...",
        "train.recording": "Recording... {seconds}s remaining",
        "train.finishing": "Finishing up...",
        "train.accepting": "Accepting training...",
        "train.retrying": "Retrying training...",
        "train.succeeded": "Training Succeeded! Good data quality.",
        "train.failed": "Training Failed! Poor data quality.",
        "train.complete": "All training complete! Saving profile...",
        "train.accept": "Accept",
        "train.reject": "Reject (Retry)",
        "train.retry": "Retry",
        "train.finish": "Finish & Go to Test Controls",

        # ── Virtual flight test ──────────────────────────────────────────────
        "test.title": "Step 2: Test Virtual Flight Controls",
        "test.subtitle": (
            "Practice moving your head and thinking commands before flying the real drone."
        ),
        "test.state_group": "Virtual Drone State",
        "test.landed": "🛫 Status: Landed",
        "test.flying": "🛸 Status: Flying",
        "test.last_command_none": "Last Mental Command: None",
        "test.last_command": "Last Mental Command: {action}",
        "test.last_command_ignored": "Last Mental Command: {action} (Ignored)",
        "test.rc_group": "Motion Tracking (RC Channels)",
        "test.yaw": "Left/Right (Yaw):",
        "test.pitch": "Fwd/Back (Pitch):",
        "test.raw_group": "Raw Stream Data",
        "test.back": "⬅ Back",
        "test.fullscreen": "📺 Fullscreen",
        "test.recenter": "🎯 Recenter Headset",
        "test.next": "Next: Real Drone Setup ➔",

        # ── Drone connection ─────────────────────────────────────────────────
        "drone.title": "Step 3: Connect to DJI Tello",
        "drone.subtitle": (
            "Ensure you are connected to the drone's WiFi network before continuing."
        ),
        "drone.ready": "Ready to connect.",
        "drone.connect": "Connect to Drone",
        "drone.connecting": "Connecting to Tello WiFi...",
        "drone.sim_skip": "Simulation mode. Skipping real drone connection.",
        "drone.connected": "Drone connected successfully! Battery: {battery}%",
        "drone.failed": "Connection failed: {detail}",
        "drone.launch": "Launch Flight Dashboard 🚀",
        "drone.back": "⬅ Back to Test",

        # ── Flight dashboard ─────────────────────────────────────────────────
        "dash.camera": "📹 Live Camera Feed",
        "dash.telemetry": "📊 Telemetry",
        "dash.battery_empty": "Drone Batt: —",
        "dash.height_empty": "Height: —",
        "dash.temp_empty": "Temp: —",
        "dash.headset_empty": "Headset: —",
        "dash.battery": "Drone Batt: {value}%",
        "dash.height": "Height: {value}cm",
        "dash.temp": "Temp: {value}°C",
        "dash.headset": "Headset: {battery}% | Sig: {signal}/4",
        "dash.controls": "🕹️ Flight & Controls",
        "dash.takeoff": "🚀 Take Off",
        "dash.land": "🛬 Land",
        "dash.emergency": "⛔ EMERGENCY",
        "dash.recenter": "🎯 Recenter",
        "dash.drone_connected": "🟢 Drone: Connected",
        "dash.drone_sim": "🟡 Drone: Simulating",
        "dash.mc_none": "🧠 MC: None",
        "dash.mc": "🧠 MC: {action}",
        "dash.system": "System",
        "dash.hud": "📺 Fullscreen HUD",
        "dash.disconnect": "🔌 Disconnect & Quit",
        "dash.log": "📟 Log",

        # ── Simulator / HUD overlays ─────────────────────────────────────────
        "sim.score": "🏆 {score}",
        "sim.readout": "ALT {alt}m   ·   SPD {spd}",
        "sim.altitude": "ALT {alt}m",
        "sim.esc_hint": "Press ESC to exit fullscreen",
        "sim.mental_command": "🧠 {action}",
        "hud.no_signal": "NO CAMERA SIGNAL",
        "hud.esc": "ESC TO EXIT",

        "cue.neutral": "Relax — let the drone hover",
        "cue.push": "Push the drone forward",

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
        "log.bci_status": "BCI Status: {status}",
        "log.retry_access": "Retrying requestAccess with EMOTIV Cortex...",
        "log.retry_failed": "Retry failed: {detail}",
        "log.enter_profile_name": "Please enter a new profile name.",
        "log.recenter": "Manual recenter triggered.",
        "log.brainmap_ready": "Brain map received — {quality}",
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
        "auth.title": "第 1 步：连接 Cortex 并授权",
        "auth.group": "凭据",
        "auth.client_id": "Client ID：",
        "auth.client_secret": "Client Secret：",
        "auth.simulate": "模拟模式（无需头戴设备即可测试界面）",
        "auth.connect": "授权",
        "auth.retry": "重新连接",
        "auth.logs": "脑机接口连接日志：",

        # ── Step 2 · headset ─────────────────────────────────────────────────
        "headset.title": "第 2 步：选择头戴设备",
        "headset.group": "可用的头戴设备",
        "headset.awaiting_auth": "— 等待授权 —",
        "headset.connect": "连接头戴设备",
        "headset.connecting_btn": "⏳ 连接中…",
        "headset.none_found": "⚠️ 未找到头戴设备",
        "headset.item": "🎧 {id}（{status}）",
        "headset.back": "⬅ 返回授权",

        "badge.not_connected": "🔴 未连接",
        "badge.connecting": "🟡 连接中…",
        "badge.waiting_approval": "🟡 等待 EMOTIV Launcher 授权…",
        "badge.bci_active": "🟢 脑机接口：已激活",
        "badge.scan_finished": "🔴 脑机接口：扫描结束 / 未找到设备",
        "badge.profile_loaded": "🟢 🧠 配置文件「{profile}」已加载，可以起飞了！",
        "badge.status": "🟡 {status}",

        # ── Step 3 · profile ─────────────────────────────────────────────────
        "profile.title": "第 3 步：训练配置文件",
        "profile.group": "可用的配置文件",
        "profile.label": "配置文件：",
        "profile.refresh": "🔄 刷新",
        "profile.refresh.tip": "重新从 Cortex 获取配置文件列表",
        "profile.connect_first": "— 请先连接头戴设备 —",
        "profile.load": "🧠 加载所选配置文件",
        "profile.loading_btn": "⏳ 加载中…",
        "profile.hint": "连接完成后请选择一个训练配置文件。",
        "profile.new_placeholder": "新配置文件名称…",
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
        "access.default_msg": "尚未获得访问权限。请打开 EMOTIV Launcher 并批准本应用。",

        # ── EEG quality check ────────────────────────────────────────────────
        "eq.title": "脑电信号质量检查",
        "eq.subtitle": "开始训练前，请确认所有电极的接触质量良好。",
        "eq.overall_waiting": "整体信号：等待中…",
        "eq.overall": "整体信号：{quality}（{value}/4）",
        "eq.group": "电极接触质量",
        "eq.waiting_data": "等待传感器数据…",
        "eq.ok": "✅ 信号质量已满足训练要求。",
        "eq.bad": "⚠️ 请先改善电极接触，调整头戴设备后再训练。",
        "eq.back": "⬅ 返回配置文件",
        "eq.next": "开始训练 ➔",

        "quality.none": "无信号",
        "quality.very_bad": "非常差",
        "quality.bad": "差",
        "quality.poor": "较差",
        "quality.fair": "一般",
        "quality.good": "良好",
        "quality.unknown": "未知（{value}）",
        "quality.short_unknown": "？",

        # ── Training screens ─────────────────────────────────────────────────
        "train.neutral.title": "训练：中性基线",
        "train.neutral.subtitle": "请放松并保持头脑清空。无人机应保持静止。",
        "train.push.title": "训练：推（前进）指令",
        "train.push.subtitle": "注视无人机，用意念想象把它向前推。",
        "train.waiting": "等待训练开始…",
        "train.get_ready": "准备…",
        "train.recording": "记录中…剩余 {seconds} 秒",
        "train.finishing": "正在收尾…",
        "train.accepting": "正在接受训练结果…",
        "train.retrying": "正在重新训练…",
        "train.succeeded": "训练成功！数据质量良好。",
        "train.failed": "训练失败！数据质量不佳。",
        "train.complete": "全部训练完成！正在保存配置文件…",
        "train.accept": "接受",
        "train.reject": "拒绝（重试）",
        "train.retry": "重试",
        "train.finish": "完成并前往测试控制",

        # ── Virtual flight test ──────────────────────────────────────────────
        "test.title": "第 2 步：测试虚拟飞行控制",
        "test.subtitle": "在操控真实无人机之前，先练习头部动作和意念指令。",
        "test.state_group": "虚拟无人机状态",
        "test.landed": "🛫 状态：已降落",
        "test.flying": "🛸 状态：飞行中",
        "test.last_command_none": "最近的意念指令：无",
        "test.last_command": "最近的意念指令：{action}",
        "test.last_command_ignored": "最近的意念指令：{action}（已忽略）",
        "test.rc_group": "动作追踪（遥控通道）",
        "test.yaw": "左/右（偏航）：",
        "test.pitch": "前/后（俯仰）：",
        "test.raw_group": "原始数据流",
        "test.back": "⬅ 返回",
        "test.fullscreen": "📺 全屏",
        "test.recenter": "🎯 重新校准头戴设备",
        "test.next": "下一步：连接真实无人机 ➔",

        # ── Drone connection ─────────────────────────────────────────────────
        "drone.title": "第 3 步：连接 DJI Tello",
        "drone.subtitle": "继续之前，请确认电脑已连接到无人机的 WiFi 网络。",
        "drone.ready": "准备连接。",
        "drone.connect": "连接无人机",
        "drone.connecting": "正在连接 Tello WiFi…",
        "drone.sim_skip": "模拟模式，跳过真实无人机连接。",
        "drone.connected": "无人机连接成功！电量：{battery}%",
        "drone.failed": "连接失败：{detail}",
        "drone.launch": "启动飞行仪表盘 🚀",
        "drone.back": "⬅ 返回测试",

        # ── Flight dashboard ─────────────────────────────────────────────────
        "dash.camera": "📹 实时摄像画面",
        "dash.telemetry": "📊 遥测数据",
        "dash.battery_empty": "无人机电量：—",
        "dash.height_empty": "高度：—",
        "dash.temp_empty": "温度：—",
        "dash.headset_empty": "头戴设备：—",
        "dash.battery": "无人机电量：{value}%",
        "dash.height": "高度：{value} 厘米",
        "dash.temp": "温度：{value}°C",
        "dash.headset": "头戴设备：{battery}% | 信号：{signal}/4",
        "dash.controls": "🕹️ 飞行与控制",
        "dash.takeoff": "🚀 起飞",
        "dash.land": "🛬 降落",
        "dash.emergency": "⛔ 紧急停止",
        "dash.recenter": "🎯 重新校准",
        "dash.drone_connected": "🟢 无人机：已连接",
        "dash.drone_sim": "🟡 无人机：模拟中",
        "dash.mc_none": "🧠 意念指令：无",
        "dash.mc": "🧠 意念指令：{action}",
        "dash.system": "系统",
        "dash.hud": "📺 全屏 HUD",
        "dash.disconnect": "🔌 断开并退出",
        "dash.log": "📟 日志",

        # ── Simulator / HUD overlays ─────────────────────────────────────────
        "sim.score": "🏆 {score}",
        "sim.readout": "高度 {alt} 米   ·   速度 {spd}",
        "sim.altitude": "高度 {alt} 米",
        "sim.esc_hint": "按 ESC 退出全屏",
        "sim.mental_command": "🧠 {action}",
        "hud.no_signal": "无摄像信号",
        "hud.esc": "按 ESC 退出",

        "cue.neutral": "放松 — 让无人机悬停",
        "cue.push": "用意念把无人机向前推",

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
        "log.bci_status": "脑机接口状态：{status}",
        "log.retry_access": "正在向 EMOTIV Cortex 重新发送授权请求…",
        "log.retry_failed": "重试失败：{detail}",
        "log.enter_profile_name": "请输入新的配置文件名称。",
        "log.recenter": "已手动触发重新校准。",
        "log.brainmap_ready": "已获取脑图 — {quality}",
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


def bind(widget, key: str, setter: str = "setText", **params):
    """Set `widget`'s text from `key` and remember how, for later retranslation.

    Keyed by setter, so a widget can carry a label and a tooltip at once.
    """
    if not hasattr(widget, "_i18n_spec"):
        widget._i18n_spec = {}
        _REGISTRY.append(widget)
    widget._i18n_spec[setter] = (key, params)
    getattr(widget, setter)(t(key, **params))
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
                getattr(widget, setter)(t(key, **params))
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
