// Where the PRTriage API lives.
// - Page opened on your own computer (localhost): talks to the API at the same address, so running the
//   backend alone is enough and nothing quietly calls the public server.
// - Page hosted somewhere else (Vercel, GitHub Pages...): talks to the public API below.
//   Deploying your own copy? Change PUBLIC_API to its full address, no trailing slash.
(function () {
  var PUBLIC_API = "https://prtriage-api.primecloud.cloud";
  var isLocal = ["localhost", "127.0.0.1", "[::1]"].indexOf(window.location.hostname) !== -1;
  window.PRTRIAGE_API_BASE = isLocal ? "" : PUBLIC_API;
})();
