import { serve } from "std/http/server.ts";

const ES_URL = Deno.env.get("ELASTICSEARCH_URL");
const ES_INDEX = Deno.env.get("ELASTICSEARCH_INDEX_DRUGS") || "meditrack_drugs";

serve(async (req) => {
  try {
    const payload = await req.json();
    const { record, old_record, type } = payload;

    const drugId = type === "DELETE" ? old_record.id : record.id;
    const url = `${ES_URL}/${ES_INDEX}/_doc/${drugId}`;

    console.log(`[Drug-Sync] Event: ${type} | ID: ${drugId}`);

    if (type === "DELETE") {
      const res = await fetch(url, { method: "DELETE" });
      return new Response(
        JSON.stringify({ status: "deleted", code: res.status }),
        { status: 200 },
      );
    }

    const body = {
      id: record.id,
      name: record.name,
      generic_name: record.generic_name,
      category: record.category,
      description: record.description,
      stock: record.stock,
      price: record.price,
      unit: record.unit,
      manufacturer: record.manufacturer,
      updated_at: record.updated_at || new Date().toISOString(),
    };

    const res = await fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const result = await res.json();
    return new Response(JSON.stringify(result), { status: res.status });
  } catch (error) {
    // 💡 Gunakan casting (error as Error) untuk menjamin tipe data di semua versi TypeScript
    const errorMessage =
      (error as Error)?.message || "Terjadi kesalahan internal";
    console.error("[Drug-Sync Error]", errorMessage);
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500,
    });
  }
});
