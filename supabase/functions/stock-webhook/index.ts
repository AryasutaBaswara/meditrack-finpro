import { serve } from "std/http/server.ts"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

interface DrugRecord {
  id?: string;
  name?: string;
  stock?: number;
  min_stock_alert?: number;
}

interface SupabaseWebhookPayload {
  type: 'INSERT' | 'UPDATE' | 'DELETE' | 'SELECT';
  table: string;
  schema: string;
  record: DrugRecord | null;
  old_record: DrugRecord | null;
}

async function fetchWithRetry(url: string, options: RequestInit, maxRetries = 3): Promise<Response> {
  let lastError: Error | null = null;
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(url, options);
      if (response.ok) return response;
      if (response.status === 429 || (response.status >= 500 && response.status <= 599)) {
        const delay = Math.pow(2, i) * 500;
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      return response;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      const delay = Math.pow(2, i) * 500;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw lastError || new Error("Max retries reached");
}

/**
 * Logika Utama Webhook (DIPISAH AGAR BISA DI-TEST)
 */
export async function handler(req: Request): Promise<Response> {
  const requestId = crypto.randomUUID().split('-')[0];
  
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const payload: SupabaseWebhookPayload = await req.json();
    const { record, old_record, type, table } = payload;

    // GUARD: Hanya proses tabel drugs
    if (table !== 'drugs') {
      return new Response(JSON.stringify({ error: "Invalid table", request_id: requestId }), { 
        status: 403, 
        headers: { ...corsHeaders, 'Content-Type': 'application/json' } 
      });
    }

    if (type === 'UPDATE' && record) {
      // GUARD: Data harus lengkap
      if (!record.id || !record.name || typeof record.stock !== 'number') {
        return new Response(JSON.stringify({ error: "Broken record payload", request_id: requestId }), { 
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      const drugName = record.name;
      const newStock = record.stock;
      const oldStock = old_record?.stock;
      const threshold = record.min_stock_alert || 5;

      console.log(`[Event-${requestId}] Drug: ${drugName} | Change: ${oldStock ?? 'N/A'} -> ${newStock}`);

      if (newStock <= threshold) {
        console.warn(`[ALERT-${requestId}] Threshold reached (${threshold}). Triggering Broadcast...`);

        const supabaseUrl = Deno.env.get('SUPABASE_URL');
        const serviceRoleKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY');

        // Jika env vars tidak ada (saat unit test tanpa mock env), kita lempar error yang terkendali
        if (!supabaseUrl || !serviceRoleKey) {
            console.error(`[Critical-${requestId}] Missing environment variables`);
            return new Response(JSON.stringify({ error: "Server configuration error" }), { status: 500 });
        }

        const broadcastUrl = `${supabaseUrl}/realtime/v1/api/broadcast`;

        const response = await fetchWithRetry(broadcastUrl, {
          method: 'POST',
          headers: {
            'apikey': serviceRoleKey,
            'Authorization': `Bearer ${serviceRoleKey}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messages: [{
              topic: 'stock-alerts',
              event: 'low-stock',
              type: 'broadcast',
              payload: {
                drug_id: record.id,
                drug_name: drugName,
                current_stock: newStock,
                threshold: threshold,
                request_id: requestId,
                timestamp: new Date().toISOString()
              }
            }]
          })
        });

        if (!response.ok) {
          const errorBody = await response.text();
          console.error(`[Relialibility-Error-${requestId}] Final failure: ${response.status} ${errorBody}`);
        } else {
          console.log(`[Success-${requestId}] Broadcast accepted.`);
        }
      }

      return new Response(JSON.stringify({ request_id: requestId, status: "processed" }), {
        status: 200,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify({ status: "ignored", request_id: requestId }), {
      status: 200,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });

  } catch (error: unknown) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown fatal error';
    console.error(`[Critical-${requestId}] Error:`, errorMessage);
    
    return new Response(JSON.stringify({ error: errorMessage, request_id: requestId }), {
        status: 400,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }
}

// JALANKAN SERVER JIKA BUKAN DALAM MODE TEST
if (import.meta.main) {
    serve(handler);
}