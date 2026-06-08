/* ═══════════════════════════════════════════════
   Moodify — PWA Music Player
   Complete app logic: downloads, library, player
   ═══════════════════════════════════════════════ */

(() => {
"use strict";

// ── DOM refs ────────────────────────────────────
const $ = id => document.getElementById(id);

const views = {
    download: $("view-download"),
    library: $("view-library"),
    settings: $("view-settings"),
};

const dom = {
    urlInput: $("url-input"),
    urlWrap: $("url-input-wrap"),
    pasteBtn: $("paste-btn"),
    badge: $("url-badge"),
    pills: $("format-pills"),
    dlBtn: $("dl-btn"),
    progCard: $("progress-card"),
    progText: $("prog-text"),
    progPct: $("prog-pct"),
    progFill: $("prog-fill"),
    progDetail: $("prog-detail"),
    resultCard: $("result-card"),
    resultTitle: $("result-title"),
    resultSub: $("result-sub"),
    errorCard: $("error-card"),
    errorText: $("error-text"),
    libList: $("lib-list"),
    libSearch: $("lib-search"),
    libCount: $("lib-count"),
    libEmpty: $("lib-empty"),
    storageUsed: $("storage-used"),
    settingsCount: $("settings-count"),
    clearLibBtn: $("clear-lib-btn"),
    miniPlayer: $("mini-player"),
    miniFill: $("mini-fill"),
    miniBody: $("mini-body"),
    miniArt: $("mini-art"),
    miniTitle: $("mini-title"),
    miniArtist: $("mini-artist"),
    miniPlayBtn: $("mini-play-btn"),
    npOverlay: $("np-overlay"),
    npCollapse: $("np-collapse"),
    npBg: $("np-bg"),
    npArt: $("np-art"),
    npTitle: $("np-title"),
    npArtist: $("np-artist"),
    seekSlider: $("seek-slider"),
    npCurrent: $("np-current"),
    npDuration: $("np-duration"),
    btnPlay: $("btn-play"),
    btnPrev: $("btn-prev"),
    btnNext: $("btn-next"),
    btnShuffle: $("btn-shuffle"),
    btnRepeat: $("btn-repeat"),
    tabBar: $("tab-bar"),
};

// ── State ───────────────────────────────────────
let format = "mp3";
let polling = null;
let currentView = "download";
let shuffleOn = false;
let repeatOn = false;

// ── Audio Engine ────────────────────────────────
const audio = new Audio();
audio.preload = "auto";

const player = {
    queue: [],        // song IDs in play order
    index: -1,        // current index in queue
    currentId: null,
    isPlaying: false,
    duration: 0,
    seeking: false,
};

// ══════════════════════════════════════════════
// IndexedDB — Song Storage
// ══════════════════════════════════════════════

const DB_NAME = "moodify";
const DB_VER = 1;
let db = null;

function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VER);
        req.onupgradeneeded = e => {
            const d = e.target.result;
            if (!d.objectStoreNames.contains("songs")) {
                d.createObjectStore("songs", { keyPath: "id" });
            }
            if (!d.objectStoreNames.contains("audio")) {
                d.createObjectStore("audio", { keyPath: "id" });
            }
        };
        req.onsuccess = e => { db = e.target.result; resolve(db); };
        req.onerror = e => reject(e);
    });
}

function dbPut(store, data) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).put(data);
        tx.oncomplete = () => resolve();
        tx.onerror = e => reject(e);
    });
}

function dbGet(store, id) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readonly");
        const req = tx.objectStore(store).get(id);
        req.onsuccess = () => resolve(req.result);
        req.onerror = e => reject(e);
    });
}

function dbGetAll(store) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readonly");
        const req = tx.objectStore(store).getAll();
        req.onsuccess = () => resolve(req.result);
        req.onerror = e => reject(e);
    });
}

function dbDelete(store, id) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).delete(id);
        tx.oncomplete = () => resolve();
        tx.onerror = e => reject(e);
    });
}

function dbClear(store) {
    return new Promise((resolve, reject) => {
        const tx = db.transaction(store, "readwrite");
        tx.objectStore(store).clear();
        tx.oncomplete = () => resolve();
        tx.onerror = e => reject(e);
    });
}

// ══════════════════════════════════════════════
// Navigation
// ══════════════════════════════════════════════

dom.tabBar.addEventListener("click", e => {
    const tab = e.target.closest(".tab");
    if (!tab) return;
    switchView(tab.dataset.view);
});

function switchView(name) {
    currentView = name;
    Object.entries(views).forEach(([k, el]) => {
        el.classList.toggle("active", k === name);
    });
    dom.tabBar.querySelectorAll(".tab").forEach(t => {
        t.classList.toggle("active", t.dataset.view === name);
    });
    if (name === "library") renderLibrary();
    if (name === "settings") updateSettings();
}

// ══════════════════════════════════════════════
// URL Detection
// ══════════════════════════════════════════════

const URL_PATTERNS = {
    spotify_track: /^https?:\/\/open\.spotify\.com\/track\/[a-zA-Z0-9]+/,
    spotify_album: /^https?:\/\/open\.spotify\.com\/album\/[a-zA-Z0-9]+/,
    spotify_playlist: /^https?:\/\/open\.spotify\.com\/playlist\/[a-zA-Z0-9]+/,
    youtube: /^https?:\/\/(www\.)?(youtube\.com\/(watch|shorts)|youtu\.be\/|music\.youtube\.com\/watch)/,
};

const LABELS = {
    spotify_track: ["🟢", "Spotify Track"],
    spotify_album: ["💿", "Spotify Album"],
    spotify_playlist: ["📋", "Spotify Playlist"],
    youtube: ["🔴", "YouTube"],
};

function detectUrl(url) {
    url = url.trim();
    for (const [key, pat] of Object.entries(URL_PATTERNS)) {
        if (pat.test(url)) return { valid: true, key, label: LABELS[key] };
    }
    if (url.includes("spotify.com") || url.includes("youtube.com") || url.includes("youtu.be"))
        return { valid: false, key: null, label: null, hint: "Unsupported link format" };
    return { valid: false, key: null, label: null };
}

dom.urlInput.addEventListener("input", () => {
    const url = dom.urlInput.value.trim();
    if (!url) {
        dom.badge.classList.remove("show", "ok", "err");
        dom.urlWrap.classList.remove("valid", "error");
        return;
    }
    const r = detectUrl(url);
    dom.badge.classList.add("show");
    if (r.valid) {
        dom.badge.textContent = `${r.label[0]} ${r.label[1]} detected`;
        dom.badge.classList.add("ok");
        dom.badge.classList.remove("err");
        dom.urlWrap.classList.add("valid");
        dom.urlWrap.classList.remove("error");
    } else {
        dom.badge.textContent = r.hint || "Not a valid Spotify or YouTube URL";
        dom.badge.classList.add("err");
        dom.badge.classList.remove("ok");
        dom.urlWrap.classList.remove("valid");
    }
});

dom.urlInput.addEventListener("keydown", e => { if (e.key === "Enter") startDownload(); });

// ── Paste ───────────────────────────────────────
dom.pasteBtn.addEventListener("click", async () => {
    try {
        const text = await navigator.clipboard.readText();
        dom.urlInput.value = text.trim();
        dom.urlInput.dispatchEvent(new Event("input"));
    } catch { dom.urlInput.focus(); }
});

// ── Format ──────────────────────────────────────
dom.pills.addEventListener("click", e => {
    const btn = e.target.closest(".pill");
    if (!btn) return;
    dom.pills.querySelectorAll(".pill").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    format = btn.dataset.fmt;
});

// ══════════════════════════════════════════════
// Download Flow
// ══════════════════════════════════════════════

dom.dlBtn.addEventListener("click", startDownload);

async function startDownload() {
    const url = dom.urlInput.value.trim();
    const r = detectUrl(url);
    if (!r.valid) {
        dom.urlWrap.classList.add("error");
        dom.badge.textContent = "⚠ Paste a valid Spotify or YouTube link";
        dom.badge.classList.add("show", "err");
        dom.badge.classList.remove("ok");
        shake(dom.urlWrap);
        return;
    }

    hideCards();
    dom.dlBtn.disabled = true;
    dom.dlBtn.querySelector("span").textContent = "Downloading...";
    showProgress("Sending request...");

    try {
        const resp = await fetch("/api/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, format }),
        });
        const data = await resp.json();
        if (!resp.ok) { showError(data.error || "Failed"); resetBtn(); return; }

        pollStatus(data.job_id);
    } catch {
        showError("Cannot connect to server");
        resetBtn();
    }
}

function pollStatus(jobId) {
    let fakePct = 5;
    polling = setInterval(async () => {
        try {
            const resp = await fetch(`/api/status/${jobId}`);
            const d = await resp.json();

            if (d.status === "downloading" || d.status === "queued") {
                fakePct = Math.min(fakePct + Math.random() * 6, 88);
                updateProgress(fakePct, d.message || "Downloading...");
            }
            if (d.status === "done") {
                clearInterval(polling);
                updateProgress(100, "Saving to library...");
                await saveToLibrary(jobId, d);
                hideCards();
                dom.resultCard.classList.remove("hidden");
                dom.resultTitle.textContent = d.metadata?.title || d.file_name || "Downloaded!";
                dom.resultSub.textContent = "Added to your library";
                resetBtn();
                dom.urlInput.value = "";
                dom.badge.classList.remove("show");
                dom.urlWrap.classList.remove("valid");
                setTimeout(() => dom.resultCard.classList.add("hidden"), 4000);
            }
            if (d.status === "error") {
                clearInterval(polling);
                hideCards();
                showError(d.message || "Download failed");
                resetBtn();
            }
        } catch {}
    }, 1500);
}

async function saveToLibrary(jobId, statusData) {
    // Fetch the audio file
    const resp = await fetch(`/api/file/${jobId}`);
    const blob = await resp.blob();
    const meta = statusData.metadata || {};
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

    const song = {
        id,
        title: meta.title || statusData.file_name || "Unknown",
        artist: meta.artist || "Unknown Artist",
        duration: meta.duration || 0,
        thumbnail: meta.thumbnail || "",
        source: statusData.source || "unknown",
        format,
        addedAt: Date.now(),
        size: blob.size,
    };

    await dbPut("songs", song);
    await dbPut("audio", { id, blob });
}

// ── Progress UI ─────────────────────────────────
function showProgress(msg) {
    dom.progCard.classList.remove("hidden");
    dom.progText.textContent = msg;
    dom.progPct.textContent = "";
    dom.progFill.style.width = "2%";
    dom.progDetail.textContent = "";
}

function updateProgress(pct, msg) {
    dom.progCard.classList.remove("hidden");
    dom.progFill.style.width = pct + "%";
    dom.progPct.textContent = Math.round(pct) + "%";
    if (msg) {
        dom.progText.textContent = pct >= 100 ? "✓ Complete" : "Downloading...";
        const short = msg.length > 60 ? msg.slice(0, 57) + "..." : msg;
        dom.progDetail.textContent = short;
    }
}

function showError(msg) {
    dom.errorCard.classList.remove("hidden");
    dom.errorText.textContent = msg;
}

function hideCards() {
    dom.progCard.classList.add("hidden");
    dom.resultCard.classList.add("hidden");
    dom.errorCard.classList.add("hidden");
    dom.progFill.style.width = "0%";
}

function resetBtn() {
    dom.dlBtn.disabled = false;
    dom.dlBtn.querySelector("span").textContent = "Download";
}

function shake(el) {
    el.style.animation = "none";
    el.offsetHeight;
    el.style.animation = "shake .4s ease";
    setTimeout(() => el.style.animation = "", 400);
}

// Add shake keyframes
const shakeStyle = document.createElement("style");
shakeStyle.textContent = `@keyframes shake{0%,100%{transform:translateX(0)}20%{transform:translateX(-5px)}40%{transform:translateX(5px)}60%{transform:translateX(-3px)}80%{transform:translateX(3px)}}`;
document.head.appendChild(shakeStyle);

// ══════════════════════════════════════════════
// Library
// ══════════════════════════════════════════════

let allSongs = [];

async function renderLibrary(filter = "") {
    allSongs = await dbGetAll("songs");
    allSongs.sort((a, b) => b.addedAt - a.addedAt);

    const q = filter.toLowerCase();
    const filtered = q ? allSongs.filter(s =>
        s.title.toLowerCase().includes(q) || s.artist.toLowerCase().includes(q)
    ) : allSongs;

    dom.libCount.textContent = `${allSongs.length} song${allSongs.length !== 1 ? "s" : ""}`;
    dom.libEmpty.classList.toggle("hidden", filtered.length > 0);
    dom.libList.innerHTML = "";

    filtered.forEach((song, i) => {
        const row = document.createElement("div");
        row.className = "song-row" + (player.currentId === song.id ? " playing" : "");
        row.innerHTML = `
            <div class="song-art">${song.thumbnail ? `<img src="${esc(song.thumbnail)}" alt="" loading="lazy">` :
            `<svg viewBox="0 0 24 24" width="24" height="24"><path d="M9 18V5l12-2v13" stroke="#444" stroke-width="2" fill="none"/><circle cx="6" cy="18" r="3" stroke="#444" stroke-width="2" fill="none"/><circle cx="18" cy="16" r="3" stroke="#444" stroke-width="2" fill="none"/></svg>`}</div>
            <div class="song-meta">
                <div class="song-title">${esc(song.title)}</div>
                <div class="song-artist">${esc(song.artist)}</div>
            </div>
            <span class="song-dur">${fmtDur(song.duration)}</span>
            <button class="song-del" data-id="${song.id}" aria-label="Delete">
                <svg viewBox="0 0 24 24" width="16" height="16"><path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
            </button>
        `;
        row.addEventListener("click", e => {
            if (e.target.closest(".song-del")) return;
            playSong(song.id);
        });
        row.querySelector(".song-del").addEventListener("click", e => {
            e.stopPropagation();
            deleteSong(song.id);
        });
        dom.libList.appendChild(row);
    });
}

dom.libSearch.addEventListener("input", () => renderLibrary(dom.libSearch.value));

async function deleteSong(id) {
    if (player.currentId === id) { audio.pause(); player.currentId = null; hideMiniPlayer(); }
    await dbDelete("songs", id);
    await dbDelete("audio", id);
    renderLibrary(dom.libSearch.value);
    updateSettings();
}

// ══════════════════════════════════════════════
// Audio Player
// ══════════════════════════════════════════════

async function playSong(id) {
    const song = await dbGet("songs", id);
    const audioData = await dbGet("audio", id);
    if (!song || !audioData) return;

    // Revoke previous object URL
    if (audio.src && audio.src.startsWith("blob:")) {
        URL.revokeObjectURL(audio.src);
    }

    const url = URL.createObjectURL(audioData.blob);
    audio.src = url;
    audio.play();

    player.currentId = id;
    player.isPlaying = true;

    // Build queue from current library order
    player.queue = allSongs.map(s => s.id);
    player.index = player.queue.indexOf(id);

    updatePlayerUI(song);
    showMiniPlayer();
    updateMediaSession(song);
    renderLibrary(dom.libSearch.value); // Highlight playing
}

function togglePlay() {
    if (!player.currentId) return;
    if (audio.paused) { audio.play(); player.isPlaying = true; }
    else { audio.pause(); player.isPlaying = false; }
    syncPlayPauseIcons();
}

async function playNext() {
    if (!player.queue.length) return;
    let next;
    if (shuffleOn) {
        next = Math.floor(Math.random() * player.queue.length);
    } else {
        next = player.index + 1;
        if (next >= player.queue.length) next = 0;
    }
    player.index = next;
    await playSong(player.queue[next]);
}

async function playPrev() {
    if (!player.queue.length) return;
    // If more than 3s in, restart current song
    if (audio.currentTime > 3) { audio.currentTime = 0; return; }
    let prev = player.index - 1;
    if (prev < 0) prev = player.queue.length - 1;
    player.index = prev;
    await playSong(player.queue[prev]);
}

// ── Audio Events ────────────────────────────────
audio.addEventListener("timeupdate", () => {
    if (player.seeking || !audio.duration) return;
    const pct = (audio.currentTime / audio.duration) * 100;
    dom.seekSlider.value = pct;
    dom.npCurrent.textContent = fmtTime(audio.currentTime);
    dom.miniFill.style.width = pct + "%";
});

audio.addEventListener("loadedmetadata", () => {
    player.duration = audio.duration;
    dom.npDuration.textContent = fmtTime(audio.duration);
    dom.seekSlider.max = 100;
});

audio.addEventListener("ended", () => {
    if (repeatOn) { audio.currentTime = 0; audio.play(); }
    else playNext();
});

audio.addEventListener("play", () => { player.isPlaying = true; syncPlayPauseIcons(); });
audio.addEventListener("pause", () => { player.isPlaying = false; syncPlayPauseIcons(); });

// ── Seek ────────────────────────────────────────
dom.seekSlider.addEventListener("input", () => {
    player.seeking = true;
    dom.npCurrent.textContent = fmtTime((dom.seekSlider.value / 100) * (audio.duration || 0));
});
dom.seekSlider.addEventListener("change", () => {
    if (audio.duration) audio.currentTime = (dom.seekSlider.value / 100) * audio.duration;
    player.seeking = false;
});

// ── Controls ────────────────────────────────────
dom.btnPlay.addEventListener("click", togglePlay);
dom.miniPlayBtn.addEventListener("click", e => { e.stopPropagation(); togglePlay(); });
dom.btnNext.addEventListener("click", playNext);
dom.btnPrev.addEventListener("click", playPrev);
dom.btnShuffle.addEventListener("click", () => {
    shuffleOn = !shuffleOn;
    dom.btnShuffle.classList.toggle("active", shuffleOn);
});
dom.btnRepeat.addEventListener("click", () => {
    repeatOn = !repeatOn;
    dom.btnRepeat.classList.toggle("active", repeatOn);
});

// ── Now Playing Overlay ─────────────────────────
dom.miniBody.addEventListener("click", () => dom.npOverlay.classList.add("open"));
dom.npCollapse.addEventListener("click", () => dom.npOverlay.classList.remove("open"));

// ── UI Updates ──────────────────────────────────
function updatePlayerUI(song) {
    // Now Playing
    dom.npTitle.textContent = song.title;
    dom.npArtist.textContent = song.artist;
    if (song.thumbnail) {
        dom.npArt.innerHTML = `<img src="${esc(song.thumbnail)}" alt="">`;
        dom.npBg.style.background = `linear-gradient(180deg, rgba(29,185,84,.15) 0%, var(--bg) 60%)`;
    } else {
        dom.npArt.innerHTML = `<svg viewBox="0 0 24 24" width="64" height="64"><path d="M9 18V5l12-2v13" stroke="#333" stroke-width="1" fill="none"/><circle cx="6" cy="18" r="3" stroke="#333" stroke-width="1" fill="none"/><circle cx="18" cy="16" r="3" stroke="#333" stroke-width="1" fill="none"/></svg>`;
    }
    dom.npCurrent.textContent = "0:00";
    dom.npDuration.textContent = fmtTime(song.duration || 0);

    // Mini Player
    dom.miniTitle.textContent = song.title;
    dom.miniArtist.textContent = song.artist;
    if (song.thumbnail) {
        dom.miniArt.innerHTML = `<img src="${esc(song.thumbnail)}" alt="">`;
    }

    syncPlayPauseIcons();
}

function syncPlayPauseIcons() {
    const playing = player.isPlaying;
    // Now Playing
    dom.btnPlay.querySelector(".play-icon").classList.toggle("hidden", playing);
    dom.btnPlay.querySelector(".pause-icon").classList.toggle("hidden", !playing);
    // Mini Player
    dom.miniPlayBtn.querySelector(".play-icon").classList.toggle("hidden", playing);
    dom.miniPlayBtn.querySelector(".pause-icon").classList.toggle("hidden", !playing);
}

function showMiniPlayer() {
    dom.miniPlayer.classList.remove("hidden");
    document.body.classList.add("has-mini");
}

function hideMiniPlayer() {
    dom.miniPlayer.classList.add("hidden");
    document.body.classList.remove("has-mini");
    dom.npOverlay.classList.remove("open");
}

// ══════════════════════════════════════════════
// Media Session API (Lock Screen Controls)
// ══════════════════════════════════════════════

function updateMediaSession(song) {
    if (!("mediaSession" in navigator)) return;

    const artwork = song.thumbnail ? [
        { src: song.thumbnail, sizes: "512x512", type: "image/jpeg" },
    ] : [];

    navigator.mediaSession.metadata = new MediaMetadata({
        title: song.title,
        artist: song.artist,
        album: "Moodify",
        artwork,
    });

    navigator.mediaSession.setActionHandler("play", () => { audio.play(); });
    navigator.mediaSession.setActionHandler("pause", () => { audio.pause(); });
    navigator.mediaSession.setActionHandler("previoustrack", () => playPrev());
    navigator.mediaSession.setActionHandler("nexttrack", () => playNext());
    navigator.mediaSession.setActionHandler("seekto", (d) => {
        if (d.seekTime != null) audio.currentTime = d.seekTime;
    });
}

// ══════════════════════════════════════════════
// Settings
// ══════════════════════════════════════════════

async function updateSettings() {
    const songs = await dbGetAll("songs");
    const totalBytes = songs.reduce((sum, s) => sum + (s.size || 0), 0);
    dom.settingsCount.textContent = songs.length;
    dom.storageUsed.textContent = fmtSize(totalBytes);
}

dom.clearLibBtn.addEventListener("click", async () => {
    if (!confirm("Delete all songs from your library?")) return;
    audio.pause();
    player.currentId = null;
    hideMiniPlayer();
    await dbClear("songs");
    await dbClear("audio");
    renderLibrary();
    updateSettings();
});

// ══════════════════════════════════════════════
// Utilities
// ══════════════════════════════════════════════

function fmtTime(s) {
    if (!s || !isFinite(s)) return "0:00";
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
}

function fmtDur(s) {
    if (!s) return "";
    return fmtTime(s);
}

function fmtSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + " MB";
    return (bytes / 1073741824).toFixed(1) + " GB";
}

function esc(str) {
    const d = document.createElement("div");
    d.textContent = str || "";
    return d.innerHTML;
}

// ══════════════════════════════════════════════
// Service Worker Registration
// ══════════════════════════════════════════════

if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}

// ══════════════════════════════════════════════
// Init
// ══════════════════════════════════════════════

openDB().then(() => {
    renderLibrary();
    updateSettings();
    dom.urlInput.focus();
}).catch(err => console.error("DB Error:", err));

})();
