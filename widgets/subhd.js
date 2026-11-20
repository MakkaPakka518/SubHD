WidgetMetadata = {
  id: "makkapakka.subhd",
  title: "SubHD 字幕",
  version: "1.0.0",
  requiredVersion: "0.0.1",
  description: "搜索和下载 SubHD 字幕，支持电影与按集匹配。由管理面板生成，可直接导入。",
  author: "MakkaPakka",
  site: "https://subhd.tv",
  globalParams: [
    { name: "backendUrl", title: "Vercel 后端地址", type: "input", value: "__BACKEND_URL__" },
    {
      name: "language", title: "字幕语言", type: "enumeration", value: "zh",
      enumOptions: [{ title: "中文", value: "zh" }, { title: "英语", value: "en" }],
    },
  ],
  modules: [{
    id: "loadSubtitle", title: "SubHD 字幕", type: "subtitle", functionName: "loadSubtitle",
    cacheDuration: 0, requiresWebView: false,
    params: [{ name: "page", title: "结果页码", type: "page", value: "1" }],
  }],
};

var SUBHD_MODULE_TOKEN = "__MODULE_TOKEN__";

async function loadSubtitle(params = {}) {
  try {
    var backend = String(params.backendUrl || "").trim().replace(/\/+$/, "");
    if (!/^https:\/\/[^\s/?#@]+$/.test(backend)) throw new Error("请填写有效的 HTTPS 后端地址");
    var token = SUBHD_MODULE_TOKEN;
    if (!/^[a-f0-9]{64}$/.test(token)) throw new Error("请通过管理面板复制模块链接并导入");
    var type = params.type;
    if (!type) type = params.season != null || params.episode != null ? "tv" : "movie";
    if (type !== "movie" && type !== "tv") return [];
    var season = null;
    var episode = null;
    if (type === "tv") {
      season = Number(params.season);
      episode = Number(params.episode);
      if (params.season == null || params.episode == null || !Number.isInteger(season)
          || !Number.isInteger(episode) || season < 0 || season > 99 || episode < 1 || episode > 999) return [];
    }
    var imdbId = String(params.imdbId || "");
    if (imdbId && !/^tt\d{7,10}$/.test(imdbId)) return [];
    if (!imdbId && /^\d+$/.test(String(params.tmdbId || ""))) {
      var external = await Widget.tmdb.get(type + "/" + params.tmdbId + "/external_ids");
      imdbId = String(external.imdb_id || "");
    }
    if (!/^tt\d{7,10}$/.test(imdbId)) return [];
    var page = Number(params.page || 1);
    if (!Number.isInteger(page) || page < 1 || page > 20) return [];
    var response = await Widget.http.post(backend + "/api/search", {
      imdbId: imdbId, type: type, season: season, episode: episode,
      language: params.language === "en" ? "en" : "zh", page: page,
    }, { headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" } });
    var data = typeof response.data === "string" ? JSON.parse(response.data) : response.data;
    if (!data || !Array.isArray(data.items)) throw new Error(data && data.detail || "后端没有返回字幕列表");
    return data.items.filter(function (item) {
      return /^subhd:[A-Za-z0-9]{4,12}$/.test(String(item.id || ""))
        && typeof item.title === "string" && item.title.length > 0
        && (item.lang === "zh" || item.lang === "en")
        && typeof item.url === "string"
        && item.url.indexOf(backend + "/api/download/" + String(item.id).slice(6) + ".zip?ticket=") === 0;
    }).map(function (item) {
      return { id: item.id, title: item.title, lang: item.lang, count: item.count, url: item.url };
    });
  } catch (error) {
    console.error("[SubHD.loadSubtitle]", error.message || error);
    throw error;
  }
}

function archiveEpisodeMatches(name, season, episode) {
  var pattern = /(?:^|[^a-z0-9])(?:s(\d{1,2})[ ._-]*e(\d{1,3})|(\d{1,2})x(\d{1,3}))(?!\d)(?:[ ._]*e\d{1,3}(?!\d))*/gi;
  var match;
  var marked = false;
  while ((match = pattern.exec(name)) !== null) {
    marked = true;
    var s = Number(match[1] || match[3]);
    var e = Number(match[2] || match[4]);
    if (s === season && e === episode) return true;
    var extras = match[0].match(/e\d{1,3}/gi) || [];
    if (s === season && extras.some(function (value) { return Number(value.slice(1)) === episode; })) return true;
    var end = name.slice(pattern.lastIndex).match(/^\s*[-~]\s*(?:e)?(\d{1,3})(?!\d)/i);
    if (end && s === season && episode >= e && episode <= Number(end[1])) return true;
  }
  if (marked) return false;
  var seasons = name.match(/(?:^|[^a-z0-9])s\d{1,2}(?!\d)/gi) || [];
  if (seasons.length && !seasons.some(function (value) { return Number(value.match(/\d+/)[0]) === season; })) return false;
  var episodes = name.match(/(?:^|[^a-z0-9])(?:ep?|第)[ ._-]*\d{1,3}(?:集)?(?!\d)/gi) || [];
  return episodes.length ? episodes.some(function (value) { return Number(value.match(/\d+/)[0]) === episode; }) : true;
}

async function resolveSubtitleArchive(params = {}) {
  try {
    var files = JSON.parse(params.subtitleFiles || params.files || "[]");
    if (!Array.isArray(files)) return null;
    var season = Number(params.season);
    var episode = Number(params.episode);
    files = files.filter(function (file) {
      var path = String(file.path || "");
      if (!path || /^(?:\/|[a-z]:)|\\|(?:^|\/)\.\.(?:\/|$)/i.test(path)) return false;
      if (params.season != null && params.episode != null && !archiveEpisodeMatches(path, season, episode)) return false;
      return /\.(?:srt|ass|ssa|vtt|ttml|dfxp|smi)$/i.test(path);
    });
    var english = params.subtitleLanguage === "en";
    var preferred = files.find(function (file) {
      var name = String(file.name || file.path || "");
      return english ? /(?:^|[^a-z])(?:en|eng|english)(?:[^a-z]|$)|英文|英语/i.test(name)
        && !/简体|繁体|中文|chs|cht|zh/i.test(name)
        : /简体|简中|chs|zh[._-]?(?:cn|hans)/i.test(name);
    });
    return (preferred || files[0] || {}).path || null;
  } catch (error) {
    console.error("[SubHD.resolveSubtitleArchive]", error.message || error);
    return null;
  }
}
