import { serve } from "std/http/server.ts";

const ES_URL = Deno.env.get("ELASTICSEARCH_URL");
const ES_INDEX = Deno.env.get("ELASTICSEARCH_INDEX_DRUGS") || "meditrack_drugs";

serve(async (req) => {
  try {
    const payload = await req.json();
    const { record, old_record, type } = payload;

    const drugId = type === "DELETE" ? old_record.id : record.id;
    const updatedAt = record?.updated_at || new Date().toISOString();
    
    // 💡 Gunakan Unix Timestamp sebagai nomor versi eksternal untuk mencegah Race Condition
    const version = new Date(updatedAt).getTime();
    const url = `${ES_URL}/${ES_INDEX}/_doc/${drugId}`;
    const versionedUrl = `${url}?version_type=external&version=${version}`;

    console.log(`[Drug-Sync] Event: ${type} | ID: ${drugId} | Version: ${version}`);

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
      updated_at: updatedAt,
    };

    const res = await fetch(versionedUrl, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (res.status === 409) {
      console.warn(`[Drug-Sync Warning] Conflict detected for ID ${drugId}. Older data rejected by Elasticsearch.`);
      return new Response(JSON.stringify({ error: "Version conflict - older data rejected" }), { status: 409 });
    }

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
