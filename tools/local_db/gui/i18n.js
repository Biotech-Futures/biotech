// English-first parallel copy. API keys, option values and commands stay unchanged.
const GUI_ZH = {
  "Generation mode": "生成模式",
  "Choose one independent configuration. Switching modes preserves both sets of inputs.": "选择一种独立配置方式。切换模式会保留两边各自的输入，不会互相覆盖。",
  "Manual mode": "手动模式",
  "Automatic mode": "自动模式",
  "Manual configuration": "手动配置",
  "Automatic generation": "自动生成",
  "Set quantities, email settings and dates below, then use the manual generation button.": "在本区域逐项设置数据数量、邮件和时间，完成后点击底部「生成手动数据」。",
  "Generate manual data": "生成手动数据",
  "Generate automatic data": "生成自动数据",
  "Automatic mode uses Analytics coverage, mixed email examples and the current clock. Manual settings stay unchanged. Memberships and email recipients follow the generated audiences; their totals need not scale linearly.": "自动模式采用统计覆盖场景、混合邮件样例和当前时间，不会改写手动模式的参数。组员关系、邮件收件人明细按实际受众派生，因此这些关联行不保证同比例增长。",
  "Changing these inputs only updates this preview. Generate automatic data confirms the database reset, then generates exactly these quantities. It does not overwrite your manual settings.": "修改学生数或浮动比例只会更新本区域预览，不会自动清库。点击「生成自动数据」并确认后，才会按显示的数量清空重建当前演示库；手动模式的参数不受影响。",
  "Wait for a valid automatic preview before generating.": "请先等待有效的自动数量预览，再生成数据。",
  "Preset email recipient estimate exceeds 2,000,000 rows. Reduce the student count or random variation.": "按当前规模估算的邮件收件人明细超过 2,000,000 条，请减少学生数或浮动范围。",
  "Load into manual mode": "载入到手动模式",
  "Student-scale preset": "按学生规模生成",
  "Enter a student count and variation to calculate the whole demo dataset from the 120-student baseline.": "只填写学生数和随机浮动范围，即可按原来的 120 学生预设，自动计算整套演示数据，无需逐项填写。",
  "Target student count": "目标学生人数",
  "Students stay at this exact count. Two demo administrators are retained.": "学生数严格使用你填写的数值，不参与浮动；管理员固定保留 2 个。支持 1–10,000 人，超出邮件明细安全预算时会提示减少规模。",
  "Random variation (±%)": "随机浮动（±%）",
  "Each other quantity varies independently within this percentage, then rounds to a whole number. Use 0 for exact proportions.": "范围为 0–50%。其他每项数量分别在比例值的 ±N% 内随机浮动，再取整；非零基础项至少保留 1 条。填 0 即按固定比例计算。",
  "120-student baseline": "120 学生基准",
  "720 messages · 600 logins · 1,200 resource accesses · 12 events · 48 email batches. At 1,000 students and ±0%: 6,000 · 5,000 · 10,000 · 100 · 400.": "基准：720 消息、600 登录、1,200 次资源访问、12 活动、48 批邮件。设为 1,000 学生、±0% 时，对应 6,000、5,000、10,000、100 和 400。",
  "Calculating preset…": "正在计算预设…",
  "Randomize again": "重新随机",
  "Target students must be a whole number from 1 to 10,000.": "目标学生数必须是 1–10,000 之间的整数。",
  "Variation must be a number from 0 to 50.": "随机浮动必须是 0–50 之间的数字。",
  "Inputs changed. Waiting to calculate a new preset…": "输入已改变，正在准备计算新预设…",
  "Team 2 · Internal development tool": "Team 2 · 本地演示工具",
  "Local analytics dataset": "本地演示数据生成器",
  "Configure a deterministic dataset and load it into the project’s local Docker PostgreSQL.": "为 Admin Analytics 与 AI 助手演示配置本地样例数据。同一组参数、随机种子和数据时钟可以复现同一份数据。",
  "Local Docker only": "仅使用本机 Docker",
  "Rebuild the local demo database": "每次生成都会清空并重建当前演示库",
  "Each generation clears all existing data in the current local demo database, rebuilds its tables, and writes your configured dataset. This includes records created while trying the demo. Other databases are not changed.": "生成时会清空当前演示库的全部旧数据和应用表，包括登录验证码、手动操作等记录，再按本页配置重新建表和生成。其他数据库不受影响；中途失败会回滚本次重建。",
  "Data quantities": "数据数量",
  "Set the explicit row counts. Related profiles and memberships are derived automatically.": "设置各类基础记录的数量。角色档案、组员关系等关联数据会自动生成，所以最终数据库总行数会高于这里的数量合计。",
  "Restore defaults": "恢复默认参数",
  "Announcements & email batches": "公告与邮件批次",
  "Set announcement quantities independently. Custom batches let you control email data without sending mail.": "公告条数与邮件发送批次数分别配置。自定义批次用于构造统计样例，不会真正发送邮件。",
  "Email generation": "邮件生成模式",
  "Analytics preset": "统计演示预设",
  "Custom batches": "自定义批次",
  "Choose Custom batches to edit timing, type, result and recipients.": "需要指定时间、邮件类型、投递结果和收件人数时，请选择「自定义批次」。",
  "Total email batches": "邮件总批次数",
  "Exact total across all selected types. No additional batches are added.": "这里就是所有邮件类型合计的准确批次数，不会额外增加系统邮件批次。",
  "First batch (UTC)": "首批时间（UTC）",
  "Batches are evenly spaced from the first to the last time.": "各批次在起止时间内等间隔分布；只有一批时使用首批时间。此处填写 UTC，不是悉尼本地时间。",
  "Last batch (UTC)": "末批时间（UTC）",
  "Allow at least 1 second between batches and 20 seconds to complete the final send.": "相邻批次至少间隔 1 秒；末批至少早于下方「数据时钟」20 秒，表示该批次已完成。",
  "Recent demo data": "快速设置近期数据",
  "Use recent 24 hours": "使用最近 24 小时",
  "Sets the dataset clock to now, with batches from 23 hours ago to 5 minutes ago.": "把数据时钟设为现在，首批设为 23 小时前、末批设为 5 分钟前。适合展示滚动 24 小时邮件统计。",
  "Email type": "邮件类型",
  "Random": "随机",
  "Random email type": "随机选择邮件类型",
  "Random delivery result": "随机选择投递结果",
  "Random recipient count": "随机选择每批人数",
  "One type for every batch, or a balanced mix of all nine types.": "选择单一类型时，全部批次使用该类型；选择混合时，会在九种类型之间轮换。",
  "Delivery result": "投递结果",
  "Partially delivered splits recipients between success and failure; it requires at least two.": "部分成功至少需要 2 人：失败人数为总人数的一半向下取整，其余成功。例如 27 人＝14 成功＋13 失败。",
  "Recipients per batch": "每批收件人数",
  "Distinct active synthetic users in each batch.": "每批选取不同的活跃合成账号。同一个人可以出现在不同批次中。",
  "Each Random button fills a visible value that applies to all batches. You can edit it again before generating. Custom announcements target these recipients individually; use the Analytics preset for role/group audience examples.": "每个随机按钮只会更改旁边这一项，结果立即可见，生成前仍能修改。选定的类型、结果、人数适用于全部批次；各批次使用不同类型或结果请选「混合」。自定义公告按具体账号确定受众；要展示角色／小组受众分布，请使用统计演示预设。",
  "Data distribution": "数据分布与时间",
  "Choose a versioned scenario, then keep or change its seed and clock for a repeatable dataset.": "选择分布场景，配置随机种子和数据时钟。需要复现当前数据库时，使用下方「载入到手动模式」。",
  "Scenario": "分布场景",
  "Loading the available dataset scenarios…": "正在加载可用分布场景…",
  "Random seed": "随机种子",
  "Changes interest selection and message-sender assignment deterministically.": "用于确定兴趣选择、消息发送者等分配。相同配置与相同种子可复现；更换种子不会改变你指定的数量。",
  "Dataset clock (UTC)": "数据时钟（UTC）",
  "Moves registration, activity, resource-access, announcement, and event dates.": "所有样例时间的基准；注册、登录、资源访问、公告和活动时间会据此安排。自定义邮件的起止时间还需单独设置。",
  "Total users": "用户总数",
  "RSVP capacity": "活动报名组合上限",
  "Explicit rows": "基础记录数量合计",
  "Ready to clear and rebuild this local demo database?": "准备清空并重建当前本地演示库？",
  "After generation, reload the demo website and sign in again.": "生成成功后请刷新演示网站并重新登录。账号密码仍使用既定演示配置。",
  "Generate and verify": "生成并校验",
  "Generating…": "正在生成…",
  "Equivalent command": "等效命令行",
  "Copy": "复制命令",
  "Generation status": "生成进度",
  "Idle": "尚未开始",
  "No generation job has been submitted in this GUI session.": "本次生成器服务启动后尚未提交生成任务。现有数据库可在下方查看。",
  "Current database": "当前数据库",
  "Load its config": "载入当前库配置",
  "Refresh": "刷新状态",
  "Checking the local database…": "正在读取本地数据库状态…",
  "Runs entirely on this machine. Product code never imports from": "仅在本机运行，产品功能不依赖此工具目录：",
  "Admin users": "管理员人数",
  "Login-capable local administrators": "具有后台登录权限的本地管理员；默认演示密码为 admin123。",
  "Supervisor users": "指导教师人数",
  "School or programme supervisors": "生成学校或项目指导教师账号，以及对应的教师档案。",
  "Mentor users": "导师人数",
  "Mentors available for group assignment": "生成导师账号和可用性记录，并按场景分配给小组。",
  "Student users": "学生人数",
  "Students with profiles and permissions": "生成学生账号、档案和关联权限；默认演示密码为 student123。",
  "Groups": "小组数量",
  "Programme groups and memberships": "生成项目小组及组员关系；统计演示场景会保留未分组学生、无导师小组等样例。",
  "Chat messages": "聊天消息数",
  "Stored messages, including soft-deleted examples": "包含正常与软删除消息；Analytics 排除软删除，因此页面显示数量可能小于此处。",
  "Login events": "登录事件数",
  "Successful-login audit events": "生成成功登录的审计记录，用于活跃度、登录趋势等统计；不等于独立登录人数。",
  "Tasks": "任务数",
  "Group and individual tasks": "生成分配给小组或个人的任务记录。",
  "Resources": "资源数",
  "Resource metadata and audiences": "生成资源名称、描述及受众配置，供资源统计使用。",
  "Resource accesses": "资源访问次数",
  "Recorded resource access events; the current model does not distinguish action type.": "生成资源访问事件。同一用户可多次访问；当前模型不区分打开或下载，不能把这两个指标分别解读。",
  "Announcements": "公告条数",
  "Published programme announcements": "生成公告内容。公告条数不等于邮件批次数；同一公告可对应多次发送。",
  "Preset announcement batches": "预设公告邮件批次数",
  "Analytics preset only: adds the same number of system-email batches. Custom mode uses its exact total below.": "仅用于预设模式：还会增加等量的系统邮件批次。例如填写 24，最终合计 48 批。自定义模式使用独立的「邮件总批次数」。",
  "Events": "活动数",
  "Programme events in several formats": "生成不同形式、不同时间的项目活动，用于活动与报名样例。",
  "RSVPs": "活动报名记录数",
  "Unique event and user responses": "每个用户对每个活动最多一条报名记录，上限为「活动数 × 用户总数」。",
  "Analytics coverage": "统计覆盖场景",
  "Varied deterministic patterns designed to exercise analytics categories and edge states, including role-targeted and unattributed email deliveries.": "推荐用于 Analytics 演示：覆盖活跃／不活跃、导师分配、未分组等差异及边界情况。预设邮件还包含不同受众归属。",
  "Uniform": "均匀分布场景",
  "Legacy cyclic distributions for baseline aggregate checks; default resource counts divide evenly.": "使用循环、较均匀的分配方式，适合核对基础总量；默认资源访问量会较均匀地分配。",
  "Select the versioned distribution rules used for generated facts.": "选择生成数据时使用的分布规则。",
  "Changes deterministic assignments such as interests and message senders.": "控制兴趣和消息发送者等分配；相同参数、种子和时间可复现。",
  "Defaults to the current time. Load its config restores the previous snapshot clock for exact replay.": "新会话默认采用当前时间；载入当前库配置会恢复该快照的时间，便于准确重建。",
  "Mixed": "混合",
  "Announcement": "公告邮件",
  "Login code": "登录验证码",
  "Password reset": "密码重置",
  "Registration student": "学生注册",
  "Registration mentor": "导师注册",
  "Guardian consent request": "监护人同意请求",
  "Unread messages": "未读消息提醒",
  "Submission reminder": "作品提交提醒",
  "Rsvp reminder": "活动报名提醒",
  "All delivered": "全部成功",
  "Partially delivered": "部分成功",
  "All failed": "全部失败",
  "Users": "用户账号",
  "Role assignments": "角色分配记录",
  "Student profiles": "学生档案",
  "Mentor profiles": "导师档案",
  "Supervisor profiles": "指导教师档案",
  "Admin profiles": "管理员档案",
  "Admin scopes": "管理员权限范围",
  "Student-supervisor links": "学生与指导教师关联",
  "Mentor availability": "导师可用性记录",
  "User interests": "用户兴趣关联",
  "Memberships": "小组成员关联",
  "Messages": "聊天消息记录",
  "Resource audiences": "资源受众配置",
  "Announcement audiences": "公告受众配置",
  "Delivery summaries": "公告发送汇总",
  "Email send batches": "邮件发送批次",
  "Email recipient outcomes": "邮件收件人结果",
  "Synthetic email ownership markers": "合成邮件标记",
  "Dataset manifests": "数据集配置清单",
  "Dataset": "数据集名称",
  "Version": "生成器数据版本",
  "Fingerprint": "数据指纹（复现校验）",
  "Target": "实际目标数据库",
  "Manifest warning": "配置清单异常",
  "Detected": "已检测到数据",
  "Not generated": "尚未生成",
  "Unavailable": "不可用",
  "Generation request accepted.": "已接收生成请求。",
  "Clearing all data and application tables in the current local demo database...": "正在清空当前本地演示库的全部数据和应用表…",
  "Rebuilding tables and reference data from current project migrations...": "正在按当前项目版本重建表结构与基础数据…",
  "Writing the newly configured demo dataset...": "正在写入你配置的新数据…",
  "Database rebuilt and dataset verified. Reload the demo website and sign in again.": "数据库已重建，数据校验通过。请刷新演示网站并重新登录。",
  "Generation failed. No database reset was committed; the previous database contents were preserved.": "生成失败，本次清空未提交，原数据库内容已恢复。",
  "The background generation worker could not start.": "后台生成任务未能启动，请重新尝试。",
  "A dataset generation job is already running.": "已有生成任务正在运行，请等待当前任务完成。",
  "The local database GUI is preparing to restart.": "生成器服务正在重启，请稍后刷新页面。",
  "Random seed must be a whole decimal number.": "随机种子必须是十进制整数，不能包含空格、小数或其他符号。",
  "Dataset clock must be a complete UTC date and time.": "请填写完整的 UTC 日期和时间。",
  "Dataset clock is not a valid UTC date and time.": "日期或时间无效，请检查月份、日期和时分秒。",
  "Select one of the dataset scenarios supplied by the server.": "请选择一个有效的数据分布场景。",
  "Messages require at least one group and one participant user.": "生成消息至少需要 1 个小组和 1 名学生、导师或指导教师。",
  "Login events require at least one user.": "生成登录事件至少需要 1 个用户。",
  "Resources, announcements, and deliveries require at least one admin.": "生成资源、公告或邮件批次至少需要 1 个管理员。",
  "Resource accesses require at least one resource and one user.": "生成资源访问至少需要 1 项资源和 1 个用户。",
  "Announcement email batches require at least one announcement. Choose a system email type to generate without announcements.": "公告邮件至少需要 1 条公告；公告为 0 时，请选择一种系统邮件类型。",
  "Partially delivered requires at least 2 recipients.": "部分成功至少需要 2 个收件人。",
  "Email batches × recipients exceeds the 2,000,000-row safety limit.": "批次数 × 每批人数超过 2,000,000 条上限，请减少批次或人数。",
  "The last batch must be at or after the first, with at least 1 second between batches.": "末批不能早于首批；每两个相邻批次之间至少留出 1 秒。",
  "The last batch must be at least 20 seconds before the dataset clock. Use recent 24 hours to reset these dates.": "末批必须早于数据时钟至少 20 秒。可点击「使用最近 24 小时」重新设置时间。",
  "Tasks require at least one group or one user.": "生成任务至少需要 1 个小组或 1 个用户。",
  "RSVPs require at least one event and one user.": "生成活动报名至少需要 1 个活动和 1 个用户。",
  "RSVPs cannot exceed the number of unique event and user pairs.": "报名记录不能超过「活动数 × 用户总数」。",
  "No valid random choice for this configuration.": "当前参数下没有有效的随机选项，请先调整数量。",
  "Increase the number of active users or reduce the batch count before randomizing recipients.": "请增加活跃用户数量，或减少邮件批次数，再随机生成收件人数。",
  "The server did not provide any dataset scenarios.": "未能读取分布场景，请刷新页面或重启生成器。",
  "The server provided invalid dataset scenario metadata.": "服务器返回的分布场景格式异常，请重启生成器。",
  "Command copied.": "命令已复制。",
  "Email batches": "邮件批次数",
  "Email recipients": "每批收件人数",
  "idle": "尚未开始",
  "queued": "排队中",
  "running": "正在生成",
  "succeeded": "生成成功",
  "failed": "生成失败"
};

function chineseText(value) {
  const text = String(value).trim().replace(/\s+/g, " ");
  if (GUI_ZH[text]) return GUI_ZH[text];
  let match;
  if ((match = /^Validated local target: (.+)$/.exec(text))) return "已确认本地目标：" + match[1];
  if ((match = /^(.+) must be a whole number from 0 to (.+)\.$/.exec(text))) return (GUI_ZH[match[1]] || match[1]) + "必须是 0 到 " + match[2] + " 之间的整数。";
  if ((match = /^Recipients per batch must be between 1 and (\d+) active synthetic users\.$/.exec(text))) return "每批人数必须在 1 到 " + match[1] + " 之间，仅使用活跃合成账号。";
  if ((match = /^Request failed with HTTP (\d+)\.$/.exec(text))) return "请求失败，HTTP 状态码：" + match[1];
  return "";
}

function inlineBilingual(value) {
  const english = String(value);
  const chinese = chineseText(english);
  return chinese ? english + " · " + chinese : english;
}

function renderBilingual(element, value) {
  const english = String(value);
  const chinese = chineseText(english);
  element.replaceChildren();
  if (chinese) {
    element.append(document.createTextNode(english));
    const secondary = document.createElement("span");
    secondary.className = "zh-copy";
    secondary.lang = "zh-CN";
    secondary.textContent = chinese;
    element.append(secondary);
  } else {
    element.textContent = english;
  }
}

function bilingualError(value) {
  const english = String(value);
  const chinese = chineseText(english);
  if (chinese) return english + "\n" + chinese;
  if (/[\u4e00-\u9fff]/.test(english)) return english;
  return english + "\n操作未完成，请根据上述信息检查参数或服务状态。";
}

function translateStaticPage() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const parent = node.parentElement;
    if (!parent || parent.closest("script, style, code, pre, [data-localized]")) continue;
    const english = node.textContent.trim().replace(/\s+/g, " ");
    const chinese = GUI_ZH[english];
    if (!chinese) continue;
    if (parent.tagName === "OPTION") {
      node.textContent = english + " · " + chinese;
    } else {
      const fragment = document.createDocumentFragment();
      fragment.append(document.createTextNode(english));
      const secondary = document.createElement("span");
      secondary.className = "zh-copy";
      secondary.lang = "zh-CN";
      secondary.textContent = chinese;
      fragment.append(secondary);
      node.replaceWith(fragment);
    }
  }
  for (const element of document.querySelectorAll("[aria-label]")) {
    element.setAttribute("aria-label", inlineBilingual(element.getAttribute("aria-label")));
  }
}
