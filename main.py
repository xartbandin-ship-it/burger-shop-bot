import { world, system } from "@minecraft/server";

console.warn("[BurgerEmpire] СИСТЕМА ЗАПУЩЕНА (BETA APIs 2.11.0-beta)...");

const ADMIN_NAME = "BurgerTheMan348";

const OVERWORLD_DIMENSION = "minecraft:overworld";
const NETHER_DIMENSION = "minecraft:nether";
const END_DIMENSION = "minecraft:the_end";

// Координаты спавна
const SPAWN_COORDS = { x: -338.5, y: 64, z: -6583.5 };

// Границы измерений
const BORDER_OVERWORLD = 40000;
const BORDER_NETHER = 5000;
const BORDER_END = 20000;

// Базовые лимиты
const BASE_MAX_HOMES = 3;
const BASE_MAX_TRIBE_MEMBERS = 4;
const TELEGRAM_LINK = "https://t.me/burgerchatsmp";

// Задержки и таймеры (мс)
const COMBAT_DURATION = 20 * 1000;
const RTP_COOLDOWN_MS = 15 * 1000;
const HOME_TP_COOLDOWN_MS = 15 * 1000;
const TRIBE_CREATE_COOLDOWN_MS = 30 * 60 * 1000;
const SPAWN_COOLDOWN_MS = 15 * 1000;
const TPA_COOLDOWN_MS = 10 * 1000;
const EXACT_TP_COOLDOWN_MS = 60 * 60 * 1000;

const tpaRequests = new Map();
const combatTimers = new Map();
const rtpCooldowns = new Map();
const homeTpCooldowns = new Map();
const spawnCooldowns = new Map();
const tpaCooldowns = new Map();
const tribeCreateCooldowns = new Map();
const tribeInvites = new Map();
const pendingConfirmations = new Map();
const borderMsgCooldown = new Map();
const lastAttackerMap = new Map();

// === ПРОВЕРКА ДОНАТА ===
function isPlus(player) {
  return player.hasTag("donor_plus") || player.hasTag("donor_plus_plus") || isAdmin(player);
}

function isPlusPlus(player) {
  return player.hasTag("donor_plus_plus") || isAdmin(player);
}

function getMaxHomes(player) {
  if (isPlusPlus(player)) return 7;
  if (isPlus(player)) return 5;
  return BASE_MAX_HOMES;
}

function getRtpRadius(player) {
  if (isPlusPlus(player)) return 30000;
  if (isPlus(player)) return 25000;
  return 20000;
}

// === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
function playSoundSafe(player, soundId) {
  try {
    player.playSound(soundId, { volume: 0.8, pitch: 1.0 });
  } catch (e) {}
}

function getSafeDimension(dimId) {
  try {
    return world.getDimension(dimId);
  } catch (e) {
    const clean = dimId.replace("minecraft:", "");
    return world.getDimension(clean);
  }
}

function isAdmin(player) {
  return player.name.toLowerCase() === ADMIN_NAME.toLowerCase();
}

function findOnlinePlayer(nameQuery) {
  if (!nameQuery) return null;
  const clean = nameQuery.trim().toLowerCase();
  const all = [...world.getAllPlayers()];

  let match = all.find((p) => p.name.toLowerCase() === clean);
  if (match) return match;
  match = all.find((p) => p.name.toLowerCase().startsWith(clean));
  if (match) return match;
  match = all.find((p) => p.name.toLowerCase().includes(clean));
  return match || null;
}

// === ГЛОБАЛЬНАЯ СТАТИСТИКА ===
function getGlobalStatsData() {
  try {
    const raw = world.getDynamicProperty("burger_stats_global_db");
    return raw ? JSON.parse(raw) : {};
  } catch (e) { return {}; }
}
function saveGlobalStatsData(data) {
  try { world.setDynamicProperty("burger_stats_global_db", JSON.stringify(data)); } catch (e) {}
}
function getPlayerStats(playerName) {
  const db = getGlobalStatsData();
  const clean = playerName.trim().toLowerCase();
  for (const key of Object.keys(db)) {
    if (key.toLowerCase() === clean || key.toLowerCase().includes(clean)) {
      return { name: key, ...db[key] };
    }
  }
  return { name: playerName, kills: 0, deaths: 0, playtime: 0 };
}
function addKill(playerName) {
  const db = getGlobalStatsData();
  let key = playerName;
  for (const k of Object.keys(db)) {
    if (k.toLowerCase() === playerName.toLowerCase()) { key = k; break; }
  }
  if (!db[key]) db[key] = { kills: 0, deaths: 0, playtime: 0 };
  db[key].kills = (db[key].kills || 0) + 1;
  saveGlobalStatsData(db);
}
function addDeath(playerName) {
  const db = getGlobalStatsData();
  let key = playerName;
  for (const k of Object.keys(db)) {
    if (k.toLowerCase() === playerName.toLowerCase()) { key = k; break; }
  }
  if (!db[key]) db[key] = { kills: 0, deaths: 0, playtime: 0 };
  db[key].deaths = (db[key].deaths || 0) + 1;
  saveGlobalStatsData(db);
}
function addPlaytimeSecond(playerName) {
  const db = getGlobalStatsData();
  let key = playerName;
  for (const k of Object.keys(db)) {
    if (k.toLowerCase() === playerName.toLowerCase()) { key = k; break; }
  }
  if (!db[key]) db[key] = { kills: 0, deaths: 0, playtime: 0 };
  db[key].playtime = (db[key].playtime || 0) + 1;
  saveGlobalStatsData(db);
}
function formatPlaytime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h}ч ${m}м ${s}с`;
}

// === БАЗА ДАННЫХ ДОМОВ И ПЛЕМЕН ===
function getGlobalHomesData() {
  try {
    const raw = world.getDynamicProperty("all_players_homes_db");
    return raw ? JSON.parse(raw) : {};
  } catch (e) { return {}; }
}
function saveGlobalHomesData(data) {
  try { world.setDynamicProperty("all_players_homes_db", JSON.stringify(data)); } catch (e) {}
}
function getHomes(player) {
  try {
    const raw = player.getDynamicProperty("saved_homes_data");
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return getGlobalHomesData()[player.name] || {};
}
function saveHomes(player, homes) {
  try { player.setDynamicProperty("saved_homes_data", JSON.stringify(homes)); } catch (e) {}
  const db = getGlobalHomesData();
  db[player.name] = homes;
  saveGlobalHomesData(db);
}
function getPlayerHomesDirect(playerName) {
  const onlinePlayer = findOnlinePlayer(playerName);
  if (onlinePlayer) return { foundName: onlinePlayer.name, homes: getHomes(onlinePlayer) };
  const db = getGlobalHomesData();
  const lower = playerName.trim().toLowerCase();
  for (const key of Object.keys(db)) {
    if (key.toLowerCase() === lower || key.toLowerCase().includes(lower)) {
      return { foundName: key, homes: db[key] };
    }
  }
  return { foundName: playerName, homes: {} };
}
function updatePlayerHomesDirect(playerName, homes) {
  const db = getGlobalHomesData();
  let matchedKey = playerName;
  for (const key of Object.keys(db)) {
    if (key.toLowerCase() === playerName.toLowerCase()) { matchedKey = key; break; }
  }
  db[matchedKey] = homes;
  saveGlobalHomesData(db);
}

function getTribesData() {
  try {
    const raw = world.getDynamicProperty("tribes_global_data");
    return raw ? JSON.parse(raw) : {};
  } catch (e) { return {}; }
}
function saveTribesData(data) {
  try { world.setDynamicProperty("tribes_global_data", JSON.stringify(data)); } catch (e) {}
}
function getPlayerTribe(playerName) {
  const tribes = getTribesData();
  for (const [tName, tInfo] of Object.entries(tribes)) {
    if (tInfo.leader.toLowerCase() === playerName.toLowerCase()) return { name: tName, role: "Лидер", ...tInfo };
    if (tInfo.members.some((m) => m.toLowerCase() === playerName.toLowerCase())) return { name: tName, role: "Участник", ...tInfo };
  }
  return null;
}

// === БОЕВОЙ РЕЖИМ (PVP) ===
function tagCombat(player) {
  const alreadyInCombat = isPlayerInCombat(player);
  combatTimers.set(player.name, Date.now() + COMBAT_DURATION);
  if (!alreadyInCombat) {
    player.sendMessage("§c[!] PvP Бой! Не выходите из игры (20 сек).");
    playSoundSafe(player, "note.bass");
  }
}
function isPlayerInCombat(player) {
  const expireTime = combatTimers.get(player.name);
  if (!expireTime) return false;
  if (Date.now() >= expireTime) { combatTimers.delete(player.name); return false; }
  return true;
}
function getCombatSecondsLeft(player) {
  const expireTime = combatTimers.get(player.name);
  if (!expireTime) return 0;
  const left = Math.ceil((expireTime - Date.now()) / 1000);
  return left > 0 ? left : 0;
}
function checkCooldown(map, key) {
  const expireTime = map.get(key);
  if (!expireTime) return 0;
  const left = Math.ceil((expireTime - Date.now()) / 1000);
  if (left > 0) return left;
  map.delete(key);
  return 0;
}
function setCooldown(map, key, ms) {
  map.set(key, Date.now() + ms);
}

// === УНИЧТОЖЕНИЕ МЕШОЧКОВ ===
world.afterEvents.entitySpawn.subscribe((ev) => {
  try {
    const entity = ev.entity;
    if (entity && entity.typeId === "minecraft:item") {
      const itemComp = entity.getComponent("minecraft:item");
      if (itemComp?.itemStack?.typeId?.includes("bundle")) { entity.kill(); }
    }
  } catch (e) {}
});

// === ПЕРЕХВАТЧИК ЧАТА ===
world.beforeEvents.chatSend.subscribe((ev) => {
  const msg = ev.message ? ev.message.trim() : "";
  const player = ev.sender;
  if (!player || !msg) return;

  const pending = pendingConfirmations.get(player.name);
  if (pending) {
    const isConfirming = msg.toLowerCase() === "!confirm" || msg.toLowerCase() === "!подтвердить";
    if (!isConfirming) {
      pendingConfirmations.delete(player.name);
      system.run(() => { try { player.sendMessage("§e[!] Действие отменено."); } catch (e) {} });
    }
  }

  if (msg.startsWith("!") || msg.startsWith("/")) {
    ev.cancel = true;
    system.run(() => {
      try { executeCommand(player, msg); } catch (err) { console.warn("[Command Error] " + err); }
    });
    return;
  }

  ev.cancel = true;
  let donorPrefix = "";
  if (isPlusPlus(player)) { donorPrefix = "§6[++] "; } 
  else if (isPlus(player)) { donorPrefix = "§b[+] "; }

  const tribe = getPlayerTribe(player.name);
  const tribePrefix = tribe ? `§8[§6${tribe.name}§8] ` : "";
  const formattedChat = `${donorPrefix}${tribePrefix}§f<§e${player.name}§f> §7${msg}`;

  system.run(() => { try { world.sendMessage(formattedChat); } catch (e) {} });
});

// Защита спавнеров
world.beforeEvents.playerBreakBlock.subscribe((ev) => {
  try {
    const block = ev.block;
    if (block && (block.typeId === "minecraft:mob_spawner" || block.typeId === "minecraft:spawner")) {
      ev.cancel = true;
      system.run(() => {
        try {
          ev.player.sendMessage("§c[!] Спавнеры защищены от разрушения!");
          playSoundSafe(ev.player, "note.bass");
        } catch (e) {}
      });
    }
  } catch (e) {}
});

// === ДВИЖОК КОМАНД ===
function executeCommand(player, commandString) {
  const raw = commandString.trim();
  const cleaned = raw.replace(/^(!|\/)/, "").trim();
  const firstSpaceIndex = cleaned.indexOf(" ");

  const cmd = (firstSpaceIndex === -1 ? cleaned : cleaned.slice(0, firstSpaceIndex)).toLowerCase();
  const fullArgs = firstSpaceIndex === -1 ? "" : cleaned.slice(firstSpaceIndex + 1).trim();
  const parts = fullArgs.split(" ").filter(Boolean);

  if (cmd === "kill") {
    if (!isPlusPlus(player)) { player.sendMessage("§c[!] Команда !kill доступна только для доната [++]."); return; }
    if (isPlayerInCombat(player)) { player.sendMessage("§c[!] Нельзя совершить самоубийство во время боя!"); return; }
    player.kill();
    player.sendMessage("§eВы совершили самоубийство.");
    return;
  }

  if (cmd === "help" || cmd === "хелп" || cmd === "commands" || cmd === "помощь") {
    const maxH = getMaxHomes(player);
    const rtpRad = getRtpRadius(player);

    let helpText =
      "§6====== КОМАНДЫ СЕРВЕРА ======\n" +
      "§e!spawn §7- Телепорт на спавн\n" +
      `§e!rtp §7- Случайный телепорт (${rtpRad / 1000}k)\n` +
      "§e!rtpnether §7- RTP в Незере (5k)\n";

    if (isPlusPlus(player)) { helpText += "§d!rtpend §7- RTP в Краю (Энде) [++]\n"; }

    helpText +=
      `§e!sethome <1-${maxH}> §7- Поставить точку дома\n` +
      `§e!home <1-${maxH}> §7- Телепорт домой\n` +
      `§e!delhome <1-${maxH}> §7- Удалить точку дома\n` +
      "§e!homes §7- Список ваших домов\n" +
      "§e!tp <ник> §7- Запрос на ТП к игроку\n";

    if (isPlusPlus(player)) {
      helpText += "§6!tp <X> <Z> §7- ТП по точным координатам (<30k, КД 1ч) [++]\n" + "§6!kill §7- Самоубийство [++]\n";
    }

    helpText +=
      "§e!tpaccept / !tpdeny §7- Принять/отклонить ТП\n" +
      "§e!stats [ник] §7- Статистика игрока\n" +
      "§e!nv §7- Ночное зрение (2ч)\n" +
      "§e!rules §7- Правила сервера\n" +
      "§e!online §7- Игроки онлайн\n" +
      "§e!tg §7- Наш Telegram чат\n";

    player.sendMessage(helpText);
    playSoundSafe(player, "random.orb");
    return;
  }

  if (cmd === "rtpend") {
    if (!isPlusPlus(player)) { player.sendMessage("§c[!] RTP в Энде доступно только для доната [++]."); return; }
    if (isPlayerInCombat(player)) { player.sendMessage(`§c[!] Вы в бою! Подождите ${getCombatSecondsLeft(player)} сек.`); return; }
    const cd = checkCooldown(rtpCooldowns, player.name);
    if (cd > 0) { player.sendMessage(`§c[!] Подождите §e${cd} сек.`); return; }
    setCooldown(rtpCooldowns, player.name, RTP_COOLDOWN_MS);

    const signX = Math.random() < 0.5 ? -1 : 1;
    const signZ = Math.random() < 0.5 ? -1 : 1;
    const randX = signX * (1200 + Math.floor(Math.random() * 6800));
    const randZ = signZ * (1200 + Math.floor(Math.random() * 6800));

    player.teleport({ x: randX + 0.5, y: 100, z: randZ + 0.5 }, { dimension: getSafeDimension(END_DIMENSION) });
    player.addEffect("slow_falling", 400, { amplifier: 1, showParticles: false });
    player.sendMessage(`§d[++] Энд RTP: §eX: ${randX}, Z: ${randZ}`);
    playSoundSafe(player, "mob.endermen.portal");
    return;
  }

  if (cmd === "stats") {
    let targetName = player.name;
    if (fullArgs) {
      const online = findOnlinePlayer(fullArgs);
      targetName = online ? online.name : fullArgs;
    }
    const stats = getPlayerStats(targetName);
    const kdr = stats.deaths === 0 ? stats.kills.toFixed(2) : (stats.kills / stats.deaths).toFixed(2);
    const tribe = getPlayerTribe(stats.name);
    const tribeDisplay = tribe ? `§e[${tribe.name}] §7(${tribe.role})` : "§7Нет";

    player.sendMessage(
      `§6=== СТАТИСТИКА: §e${stats.name} §6===\n` +
      `§fПлемя: ${tribeDisplay}\n` +
      `§aУбийств: §f${stats.kills}\n` +
      `§cСмертей: §f${stats.deaths}\n` +
      `§eK/D: §f${kdr}\n` +
      `§bВремя в игре: §f${formatPlaytime(stats.playtime)}\n` +
      `§6=============================`
    );
    playSoundSafe(player, "random.orb");
    return;
  }

  if (cmd === "confirm" || cmd === "подтвердить") { handleConfirmation(player); return; }

  if (cmd === "online") {
    const allPlayers = [...world.getAllPlayers()];
    const namesList = allPlayers.map((p) => {
      let tag = "";
      if (isPlusPlus(p)) tag = "§6[++] ";
      else if (isPlus(p)) tag = "§b[+] ";
      const tribe = getPlayerTribe(p.name);
      return tribe ? `${tag}§8[§6${tribe.name}§8] §e${p.name}` : `${tag}§e${p.name}`;
    }).join("§7, ");
    player.sendMessage(`§6=== ОНЛАЙН (${allPlayers.length}) ===\n${namesList || "§7..."}\n§6====================`);
    playSoundSafe(player, "random.orb");
    return;
  }

  if (cmd === "rules" || cmd === "правила") {
    player.sendMessage("§6=== ПРАВИЛА СЕРВЕРА ===\n§e1. §fЗапрещен гриф спавна\n§e2. §fЗапрещено PvP на спавне\n§e3. §fЗапрещены читы\n§6=======================");
    playSoundSafe(player, "random.orb");
    return;
  }

  if (cmd === "nv") {
    player.addEffect("night_vision", 144000, { amplifier: 0, showParticles: false });
    player.sendMessage("§a[+] Ночное зрение выдано на 2 часа!");
    playSoundSafe(player, "random.orb");
    return;
  }

  if (cmd === "tg") {
    player.sendMessage(`§bНаш Telegram: §a${TELEGRAM_LINK}`);
    playSoundSafe(player, "random.orb");
    return;
  }

  // --- КЛАНЫ ---
  if (cmd === "tribe" || cmd === "клан") {
    const sub = (parts[0] || "").toLowerCase();
    const playerTribe = getPlayerTribe(player.name);

    if (!sub || sub === "info") {
      if (!playerTribe) { player.sendMessage("§7Вы не состоите в племени."); return; }
      const membersList = [playerTribe.leader, ...playerTribe.members].join("§7, §a");
      player.sendMessage(`§6=== [${playerTribe.name}] ===\n§fРоль: §e${playerTribe.role}\n§fЛидер: §e${playerTribe.leader}\n§fУчастники: §a${membersList}\n§6====================`);
      return;
    }
    if (sub === "create") {
      const tribeName = parts[1] || "";
      if (checkCooldown(tribeCreateCooldowns, player.name) > 0) { player.sendMessage("§c[!] Подождите перед созданием племени."); return; }
      if (!tribeName || tribeName.length > 12) { player.sendMessage("§c[!] Название до 12 символов."); return; }
      if (playerTribe) { player.sendMessage("§c[!] Вы уже в племени!"); return; }
      const tribes = getTribesData();
      if (Object.keys(tribes).some((k) => k.toLowerCase() === tribeName.toLowerCase())) { player.sendMessage("§c[!] Имя занято!"); return; }
      setCooldown(tribeCreateCooldowns, player.name, TRIBE_CREATE_COOLDOWN_MS);
      tribes[tribeName] = { leader: player.name, members: [] };
      saveTribesData(tribes);
      world.sendMessage(`§6[+] Игрок §e${player.name} §6основал племя §e[${tribeName}]§6!`);
      playSoundSafe(player, "random.orb");
      return;
    }
    if (sub === "invite") {
      const targetQuery = parts.slice(1).join(" ");
      if (!playerTribe || playerTribe.leader.toLowerCase() !== player.name.toLowerCase()) { player.sendMessage("§c[!] Только для лидера."); return; }
      let maxTribeSlots = BASE_MAX_TRIBE_MEMBERS;
      if (isPlusPlus(player)) maxTribeSlots = 8;
      else if (isPlus(player)) maxTribeSlots = 6;

      if (1 + playerTribe.members.length >= maxTribeSlots) { player.sendMessage(`§c[!] Лимит слотов (${maxTribeSlots}) исчерпан!`); return; }
      const target = findOnlinePlayer(targetQuery);
      if (!target) { player.sendMessage("§c[!] Игрок не найден."); return; }
      tribeInvites.set(target.name, playerTribe.name);
      player.sendMessage(`§a[+] Приглашение отправлено §e${target.name}`);
      target.sendMessage(`§6[!] Вас пригласили в §e[${playerTribe.name}]§6! Введите §e!tribe join`);
      playSoundSafe(target, "random.orb");
      return;
    }
    if (sub === "join") {
      const invitedTribeName = tribeInvites.get(player.name);
      if (!invitedTribeName || playerTribe) { player.sendMessage("§c[!] Нет приглашений."); return; }
      const tribes = getTribesData();
      const tInfo = tribes[invitedTribeName];
      if (!tInfo) { player.sendMessage("§c[!] Племя удалено."); return; }
      tInfo.members.push(player.name);
      saveTribesData(tribes);
      tribeInvites.delete(player.name);
      world.sendMessage(`§a[+] §e${player.name} §aвступил в племя §e[${invitedTribeName}]`);
      playSoundSafe(player, "random.orb");
      return;
    }
    if (sub === "leave") {
      if (!playerTribe) { player.sendMessage("§7Вы не в племени."); return; }
      const tribes = getTribesData();
      if (playerTribe.leader.toLowerCase() === player.name.toLowerCase()) {
        delete tribes[playerTribe.name];
        world.sendMessage(`§c[-] Племя §e[${playerTribe.name}] §cраспущено.`);
      } else {
        tribes[playerTribe.name].members = tribes[playerTribe.name].members.filter((m) => m.toLowerCase() !== player.name.toLowerCase());
        world.sendMessage(`§e${player.name} §7покинул племя.`);
      }
      saveTribesData(tribes);
      return;
    }
    if (sub === "list") {
      const tribes = getTribesData();
      const list = Object.keys(tribes);
      player.sendMessage(list.length === 0 ? "§7Нет племен." : "§6=== ПЛЕМЕНА ===\n§b" + list.join("§7, §b"));
      return;
    }
    return;
  }

  // Защита ТП в бою
  const tpCommands = ["spawn", "rtp", "rtpnether", "rtpend", "home", "tp", "tpa", "tpaccept"];
  if (tpCommands.includes(cmd) && isPlayerInCombat(player)) {
    player.sendMessage(`§c[!] В бою! Подождите ${getCombatSecondsLeft(player)} сек.`);
    playSoundSafe(player, "note.bass");
    return;
  }

  if (cmd === "spawn") {
    const cd = checkCooldown(spawnCooldowns, player.name);
    if (cd > 0) { player.sendMessage(`§c[!] Подождите §e${cd} сек.`); return; }
    setCooldown(spawnCooldowns, player.name, SPAWN_COOLDOWN_MS);
    player.teleport(SPAWN_COORDS, { dimension: getSafeDimension(OVERWORLD_DIMENSION) });
    player.sendMessage("§a[+] Телепортация на спавн!");
    playSoundSafe(player, "mob.endermen.portal");
    return;
  }

  if (cmd === "rtp") {
    const cd = checkCooldown(rtpCooldowns, player.name);
    if (cd > 0) { player.sendMessage(`§c[!] Подождите §e${cd} сек.`); return; }
    setCooldown(rtpCooldowns, player.name, RTP_COOLDOWN_MS);
    const radius = getRtpRadius(player);
    const targetX = Math.floor(Math.random() * (radius * 2)) - radius;
    const targetZ = Math.floor(Math.random() * (radius * 2)) - radius;
    player.teleport({ x: targetX + 0.5, y: 180, z: targetZ + 0.5 }, { dimension: getSafeDimension(OVERWORLD_DIMENSION) });
    player.addEffect("slow_falling", 300, { amplifier: 1, showParticles: false });
    player.sendMessage(`§a[+] RTP: §eX: ${targetX}, Z: ${targetZ}`);
    playSoundSafe(player, "mob.endermen.portal");
    return;
  }

  if (cmd === "rtpnether") {
    const cd = checkCooldown(rtpCooldowns, player.name);
    if (cd > 0) { player.sendMessage(`§c[!] Подождите §e${cd} сек.`); return; }
    setCooldown(rtpCooldowns, player.name, RTP_COOLDOWN_MS);
    const randX = Math.floor(Math.random() * (5000 * 2)) - 5000;
    const randZ = Math.floor(Math.random() * (5000 * 2)) - 5000;
    player.teleport({ x: randX + 0.5, y: 68, z: randZ + 0.5 }, { dimension: getSafeDimension(NETHER_DIMENSION) });
    player.addEffect("fire_resistance", 1200, { amplifier: 0, showParticles: false });
    player.addEffect("slow_falling", 300, { amplifier: 1, showParticles: false });
    player.sendMessage(`§c[+] Незер RTP (5k): §eX: ${randX}, Y: 68, Z: ${randZ}`);
    playSoundSafe(player, "mob.endermen.portal");
    return;
  }

  if (cmd === "sethome") { initiateSetHome(player, parts[0] || "1"); return; }
  if (cmd === "home") {
    const slot = parts[0] || "1";
    const cd = checkCooldown(homeTpCooldowns, player.name);
    if (cd > 0) { player.sendMessage(`§c[!] Подождите §e${cd} сек.`); return; }
    const homes = getHomes(player);
    const target = homes[slot];
    if (!target) { player.sendMessage(`§c[!] Дом §e[${slot}] §cне найден.`); return; }
    setCooldown(homeTpCooldowns, player.name, HOME_TP_COOLDOWN_MS);
    player.teleport({ x: target.x + 0.5, y: target.y + 0.5, z: target.z + 0.5 }, { dimension: getSafeDimension(target.dimension || OVERWORLD_DIMENSION) });
    player.sendMessage(`§a[+] ТП в дом §e[${slot}]`);
    playSoundSafe(player, "mob.endermen.portal");
    return;
  }
  if (cmd === "delhome") { initiateDelHome(player, parts[0] || "1"); return; }
  if (cmd === "homes") {
    const keys = Object.keys(getHomes(player));
    player.sendMessage(keys.length === 0 ? "§7Нет домов." : `§aВаши дома: §e${keys.join("§7, §e")}`);
    return;
  }

  if (cmd === "tp" || cmd === "tpa") {
    if (parts.length >= 2 && !isNaN(parseInt(parts[0])) && !isNaN(parseInt(parts[1]))) {
      handleExactCoordsTp(player, parseInt(parts[0]), parseInt(parts[1]));
      return;
    }
    handleTpaRequest(player, fullArgs);
    return;
  }

  if (cmd === "tpaccept") { handleTpaResponse(player, true); return; }
  if (cmd === "tpdeny") { handleTpaResponse(player, false); return; }

  player.sendMessage("§c[!] Неизвестная команда. Напишите: !help");
  playSoundSafe(player, "note.bass");
}

function handleExactCoordsTp(player, targetX, targetZ) {
  if (!isPlusPlus(player)) { player.sendMessage("§c[!] Доступно только для [++]."); return; }
  if (player.dimension.id !== OVERWORLD_DIMENSION) { player.sendMessage("§c[!] Только в Обычном мире!"); return; }
  if (Math.abs(targetX) > 30000 || Math.abs(targetZ) > 30000) { player.sendMessage("§c[!] До 30 000 блоков!"); return; }

  const lastTp = player.getDynamicProperty("exact_tp_timestamp") || 0;
  const now = Date.now();
  if (now - lastTp < EXACT_TP_COOLDOWN_MS) {
    const leftMin = Math.ceil((EXACT_TP_COOLDOWN_MS - (now - lastTp)) / 60000);
    player.sendMessage(`§c[!] Перезарядка: §e${leftMin} мин.`);
    return;
  }
  player.setDynamicProperty("exact_tp_timestamp", now);
  player.teleport({ x: targetX + 0.5, y: 150, z: targetZ + 0.5 }, { dimension: player.dimension });
  player.addEffect("slow_falling", 400, { amplifier: 1, showParticles: false });
  player.sendMessage(`§6[++] ТП на координаты: §eX: ${targetX}, Z: ${targetZ}`);
  playSoundSafe(player, "mob.endermen.portal");
}

function initiateSetHome(player, name) {
  const dim = player.dimension.id.toLowerCase();
  if (dim.includes("the_end") && !isPlus(player)) { player.sendMessage("§c[!] Дома в Энде только для [+] и [++]."); return; }
  const homes = getHomes(player);
  const maxAllowed = getMaxHomes(player);

  if (homes[name]) {
    pendingConfirmations.set(player.name, { type: "sethome", name: name, timestamp: Date.now() });
    player.sendMessage(`§e[!] Дом §6[${name}]§e уже есть! Напишите §a!confirm`);
    return;
  }
  if (Object.keys(homes).length >= maxAllowed) { player.sendMessage(`§c[!] Лимит домов (${maxAllowed}) достигнут!`); return; }
  saveHomeDirectly(player, name);
}

function initiateDelHome(player, name) {
  if (!getHomes(player)[name]) { player.sendMessage(`§c[!] Дом [${name}] не найден.`); return; }
  pendingConfirmations.set(player.name, { type: "delhome", name: name, timestamp: Date.now() });
  player.sendMessage(`§c[!] Удалить дом [${name}]? Напишите §a!confirm`);
}

function handleConfirmation(player) {
  const pending = pendingConfirmations.get(player.name);
  if (!pending || Date.now() - pending.timestamp > 30000) { player.sendMessage("§c[!] Нет запросов."); return; }
  pendingConfirmations.delete(player.name);
  if (pending.type === "sethome") saveHomeDirectly(player, pending.name);
  else if (pending.type === "delhome") {
    const homes = getHomes(player);
    delete homes[pending.name];
    saveHomes(player, homes);
    player.sendMessage(`§a[-] Дом [${pending.name}] удален.`);
  }
}

function saveHomeDirectly(player, name) {
  const homes = getHomes(player);
  const loc = player.location;
  homes[name] = { x: Math.round(loc.x), y: Math.round(loc.y), z: Math.round(loc.z), dimension: player.dimension.id };
  saveHomes(player, homes);
  player.sendMessage(`§a[+] Дом [${name}] сохранен!`);
  playSoundSafe(player, "random.orb");
}

function handleTpaRequest(sender, targetQuery) {
  if (!targetQuery) { sender.sendMessage("§cИспользование: !tp <ник>"); return; }
  if (checkCooldown(tpaCooldowns, sender.name) > 0) return;
  const target = findOnlinePlayer(targetQuery);
  if (!target) { sender.sendMessage("§cИгрок не найден."); return; }
  if (target.name === sender.name) { sender.sendMessage("§cНельзя к себе."); return; }
  setCooldown(tpaCooldowns, sender.name, TPA_COOLDOWN_MS);
  tpaRequests.set(target.name, { sender: sender.name, timestamp: Date.now() });
  sender.sendMessage(`§a[+] Запрос отправлен §e${target.name}`);
  target.sendMessage(`§e${sender.name} §fхочет ТП к вам. Напишите §e!tpaccept`);
  playSoundSafe(target, "random.orb");
}

function handleTpaResponse(receiver, accepted) {
  const req = tpaRequests.get(receiver.name);
  if (!req || Date.now() - req.timestamp > 60000) { receiver.sendMessage("§cНет запросов."); return; }
  tpaRequests.delete(receiver.name);
  const senderPlayer = [...world.getAllPlayers()].find((p) => p.name === req.sender);
  if (!senderPlayer) { receiver.sendMessage("§cИгрок вышел."); return; }
  if (accepted) {
    if (isPlayerInCombat(senderPlayer) || isPlayerInCombat(receiver)) { receiver.sendMessage("§cОдин из игроков в бою!"); return; }
    senderPlayer.teleport(receiver.location, { dimension: receiver.dimension });
    senderPlayer.sendMessage(`§a[+] ТП к §e${receiver.name}`);
    receiver.sendMessage("§a[+] Запрос принят.");
  } else {
    senderPlayer.sendMessage("§cЗапрос отклонен.");
  }
}

// === СОБЫТИЯ ВХОДА И СМЕРТИ ===
world.afterEvents.playerSpawn.subscribe((ev) => {
  try {
    const player = ev.player;
    if (!ev.initialSpawn) return;

    updatePlayerHomesDirect(player.name, getHomes(player));
    player.sendMessage("§a[BurgerEmpire] Добро пожаловать! Напишите §e!help §aдля списка команд.");
  } catch (err) {}
});

world.afterEvents.entityHurt.subscribe((ev) => {
  try {
    const hurtEntity = ev.hurtEntity;
    const attacker = ev.damageSource?.damagingEntity;
    if (hurtEntity?.typeId === "minecraft:player" && attacker?.typeId === "minecraft:player") {
      tagCombat(attacker);
      tagCombat(hurtEntity);
      lastAttackerMap.set(hurtEntity.name, { attackerName: attacker.name, timestamp: Date.now() });
    }
  } catch (e) {}
});

world.afterEvents.entityDie.subscribe((ev) => {
  try {
    const dead = ev.deadEntity;
    if (dead && dead.typeId === "minecraft:player") {
      addDeath(dead.name);
      combatTimers.delete(dead.name);
      let killerName = null;
      const directDamager = ev.damageSource?.damagingEntity;
      if (directDamager && directDamager.typeId === "minecraft:player" && directDamager.name !== dead.name) {
        killerName = directDamager.name;
      }
      if (killerName) addKill(killerName);
      lastAttackerMap.delete(dead.name);
    }
  } catch (e) {}
});

// === СИСТЕМНЫЙ ЦИКЛ ===
system.runInterval(() => {
  try {
    const allPlayers = [...world.getAllPlayers()];
    for (const player of allPlayers) {
      addPlaytimeSecond(player.name);

      let targetTag = player.name;
      if (isPlusPlus(player)) targetTag = `§6[++§6] §f${player.name}`;
      else if (isPlus(player)) targetTag = `§b[+§b] §f${player.name}`;
      if (player.nameTag !== targetTag) player.nameTag = targetTag;

      try {
        const container = player.getComponent("minecraft:inventory")?.container;
        if (container) {
          for (let i = 0; i < container.size; i++) {
            const item = container.getItem(i);
            if (item && item.typeId.includes("bundle")) {
              container.setItem(i, undefined);
              player.sendMessage("§c[!] Мешочки (Bundles) запрещены!");
            }
          }
        }
      } catch (err) {}

      const loc = player.location;
      const dimId = player.dimension.id.toLowerCase();
      let border = BORDER_OVERWORLD;
      if (dimId.includes("nether")) border = BORDER_NETHER;
      else if (dimId.includes("the_end") || dimId.includes("end")) border = BORDER_END;

      if (Math.abs(loc.x) > border || Math.abs(loc.z) > border) {
        const pushX = Math.min(Math.max(loc.x, -border + 4), border - 4);
        const pushZ = Math.min(Math.max(loc.z, -border + 4), border - 4);
        player.teleport({ x: pushX, y: loc.y + 0.2, z: pushZ }, { dimension: player.dimension });
        player.sendMessage(`§c[!] Граница мира (${border} блоков)!`);
      }

      if (isPlayerInCombat(player)) {
        const left = getCombatSecondsLeft(player);
        if (left > 0) player.onScreenDisplay.setActionBar(`§c⚔ В БОЮ: §e${left}s`);
      }
    }
  } catch (e) {}
}, 20);
