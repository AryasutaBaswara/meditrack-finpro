import { assertEquals } from "std/testing/asserts.ts";
import { handler } from "./index.ts";

/**
 * TEST CASE 1: Pastikan tabel selain 'drugs' ditolak (403)
 */
Deno.test("Handler should reject non-drugs tables", async () => {
    const mockRequest = new Request("http://localhost/functions/v1/stock-webhook", {
        method: "POST",
        body: JSON.stringify({
            table: "users",
            type: "UPDATE",
            record: { name: "Test" }
        })
    });

    const response = await handler(mockRequest);
    assertEquals(response.status, 403);
    const data = await response.json();
    assertEquals(data.error, "Invalid table");
});

/**
 * TEST CASE 2: Pastikan data yang tidak lengkap ditolak (400)
 */
Deno.test("Handler should reject incomplete payloads", async () => {
    const mockRequest = new Request("http://localhost/functions/v1/stock-webhook", {
        method: "POST",
        body: JSON.stringify({
            table: "drugs",
            type: "UPDATE",
            record: { name: "Paracetamol" }
        })
    });

    const response = await handler(mockRequest);
    assertEquals(response.status, 400);
    const data = await response.json();
    assertEquals(data.error, "Broken record payload");
});

/**
 * TEST CASE 3: Pastikan stok aman tidak memicu broadcast (200 status processed/ignored)
 */
Deno.test("Handler should ignore stock values above threshold", async () => {
    const mockRequest = new Request("http://localhost/functions/v1/stock-webhook", {
        method: "POST",
        body: JSON.stringify({
            table: "drugs",
            type: "UPDATE",
            record: { id: "123", name: "Paracetamol", stock: 100 },
            old_record: { stock: 102 }
        })
    });

    const response = await handler(mockRequest);
    assertEquals(response.status, 200);
    const data = await response.json();
    assertEquals(data.status, "processed"); 
});
