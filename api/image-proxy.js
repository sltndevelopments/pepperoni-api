export default async function handler(req, res) {
  const raw = Array.isArray(req.query.u) ? req.query.u[0] : req.query.u;
  if (!raw) {
    res.status(400).json({ error: "Missing u query parameter" });
    return;
  }

  let target;
  try {
    target = new URL(raw);
  } catch (_) {
    res.status(400).json({ error: "Invalid target URL" });
    return;
  }

  // Security: proxy only Cloudinary image delivery.
  if (target.hostname !== "res.cloudinary.com") {
    res.status(403).json({ error: "Host is not allowed" });
    return;
  }
  if (!target.pathname.includes("/image/upload/")) {
    res.status(403).json({ error: "Path is not allowed" });
    return;
  }

  try {
    const upstream = await fetch(target.toString(), {
      redirect: "follow",
      headers: {
        // Avoid accidental HTML variants and keep image response deterministic.
        Accept: "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
      },
    });

    if (!upstream.ok) {
      res.status(upstream.status).json({ error: "Upstream image fetch failed" });
      return;
    }

    const contentType = upstream.headers.get("content-type") || "image/jpeg";
    const arrayBuffer = await upstream.arrayBuffer();
    const body = Buffer.from(arrayBuffer);

    // Cache at edge/browser but allow controlled revalidation.
    res.setHeader("Content-Type", contentType);
    res.setHeader("Cache-Control", "public, max-age=86400, stale-while-revalidate=604800");
    res.status(200).send(body);
  } catch (err) {
    res.status(502).json({ error: "Proxy request failed" });
  }
}
