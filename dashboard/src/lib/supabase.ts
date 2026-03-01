import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

// Single shared instance — avoids "Multiple GoTrueClient instances" warning
let _client: SupabaseClient | null = null;

export function createBrowserClient(): SupabaseClient {
  if (_client) return _client;
  _client = createClient(supabaseUrl, supabaseKey, {
    realtime: { params: { eventsPerSecond: 10 } },
  });
  return _client;
}

export const supabase = createBrowserClient();
