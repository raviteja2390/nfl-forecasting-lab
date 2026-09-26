declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    ODDS_API_KEY?: string;
    BUCKET?: R2Bucket;
  }
}
