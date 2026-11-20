const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const calls = [];
const MODULE_TOKEN = "b".repeat(64);
const context = vm.createContext({
  console: { error() {} },
  Widget: {
    http: {
      post: async (url, body, options) => {
        calls.push({ url, body, options });
        return { data: { items: [
          { id: "subhd:Ab12Cd", title: "Movie", lang: "zh", count: 2, url: "https://backend.test/api/download/Ab12Cd.zip?ticket=test", internal: "discard" },
          { id: "wrong", title: "Bad", lang: "zh", url: "https://evil.test/" },
        ] } };
      },
    },
    tmdb: {
      get: async (url) => {
        calls.push({ tmdb: url });
        return { imdb_id: "tt4154796" };
      },
    },
  },
});
vm.runInContext(fs.readFileSync(path.join(__dirname, "../widgets/subhd.js"), "utf8").replace('"__MODULE_TOKEN__"', JSON.stringify(MODULE_TOKEN)), context);
const params = { backendUrl: "https://backend.test", type: "movie" };

(async () => {
  assert.equal(context.WidgetMetadata.modules[0].id, "loadSubtitle");
  assert.equal(context.WidgetMetadata.modules[0].type, "subtitle");
  const result = await context.loadSubtitle({ ...params, imdbId: "tt4154796" });
  assert.equal(result.length, 1);
  assert.deepEqual(Object.keys(result[0]).sort(), ["count", "id", "lang", "title", "url"]);
  assert.equal(result[0].lang, "zh");
  assert.equal(calls[0].url, "https://backend.test/api/search");
  assert.equal(calls[0].body.imdbId, "tt4154796");
  assert.equal(calls[0].options.headers.Authorization, "Bearer " + MODULE_TOKEN);
  calls.length = 0;
  await context.loadSubtitle({ ...params, tmdbId: 299534 });
  assert.equal(calls[0].tmdb, "movie/299534/external_ids");
  assert.equal(calls[1].body.imdbId, "tt4154796");
  calls.length = 0;
  for (const invalid of [
    { imdbId: "http://wrong/", tmdbId: 1 }, { id: "tt4154796" },
    { imdbId: "tt4154796", type: "tmdb" },
    { imdbId: "tt4154796", type: "tv", season: 1 },
  ]) {
    assert.equal((await context.loadSubtitle({ ...params, ...invalid })).length, 0);
  }
  assert.equal(calls.length, 0);
  await context.loadSubtitle({ ...params, type: "tv", imdbId: "tt0944947", season: 0, episode: 2, language: "en" });
  assert.equal(calls[0].body.season, 0);
  assert.equal(calls[0].body.episode, 2);
  assert.equal(calls[0].body.language, "en");
  const files = [
    { name: "wrong.chs.srt", path: "Show.S01E20.chs.srt" },
    { name: "Show.S01E02.en.srt", path: "Season 1/Show.S01E02.en.srt" },
    { name: "Show.S01E02.chs.ass", path: "Season 1/Show.S01E02.chs.ass" },
    { name: "escape.chs.srt", path: "../Show.S01E02.chs.srt" },
  ];
  const archive = { subtitleFiles: JSON.stringify(files), season: 1, episode: 2, subtitleLanguage: "zh" };
  assert.equal(await context.resolveSubtitleArchive(archive), files[2].path);
  assert.equal(await context.resolveSubtitleArchive({ ...archive, subtitleLanguage: "en" }), files[1].path);
  assert.equal(await context.resolveSubtitleArchive({ ...archive, episode: 99 }), null);
  assert.equal(await context.resolveSubtitleArchive({ subtitleFiles: "invalid" }), null);
  assert.equal(context.archiveEpisodeMatches("Show.S01E01-E03.srt", 1, 2), true);
  assert.equal(context.archiveEpisodeMatches("Show.S01E20.srt", 1, 2), false);
  assert.equal(context.archiveEpisodeMatches("Show.S11E02.srt", 1, 2), false);
  console.log("Widget tests passed");
})().catch((error) => { console.error(error); process.exitCode = 1; });
