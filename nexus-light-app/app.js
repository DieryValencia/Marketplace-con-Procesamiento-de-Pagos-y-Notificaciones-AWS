"use strict";

const API_BASE = "https://2uqkjsioug.execute-api.us-east-1.amazonaws.com";

// --- State Management ---
let state = {
    products: [],
    isCanary: false,
    loading: false
};

// --- DOM References ---
const grid = document.getElementById('product-grid');
const tracer = document.getElementById('status-tracer');
const tracerDesc = document.getElementById('tracer-desc');
const canaryBadge = document.getElementById('canary-badge');

// --- AWS Service Logic ---

/**
 * [RDS] Fetch Products
 */
async function loadProducts() {
    if (!grid) return;
    grid.innerHTML = Array(10).fill(0).map(() => `
        <div class="product-card rounded-xl p-3 space-y-3 h-[320px]">
            <div class="h-32 skeleton-box rounded-lg"></div>
            <div class="h-3 w-1/2 skeleton-box rounded"></div>
            <div class="h-5 w-3/4 skeleton-box rounded"></div>
            <div class="mt-auto h-8 w-full skeleton-box rounded-lg"></div>
        </div>
    `).join('');

    try {
        const res = await fetch(`${API_BASE}/api/products`);
        const data = await res.json();
        state.products = data;
        renderProducts(data);
    } catch (err) {
        console.error("Error al conectar con RDS:", err);
        renderProducts([]); // Render empty state or fallback
    }
}

/**
 * [SQS/SNS] Handle Purchase Flow
 */
async function purchaseProduct(productId) {
    toggleTracer(true, "Enviando Orden a SQS...");
    
    try {
        const res = await fetch(`${API_BASE}/create-order`, {
            method: "POST",
            body: JSON.stringify({ productId, buyerId: "light_user_" + Date.now(), amount: 100 })
        });
        const result = await res.json();
        
        tracerDesc.innerText = "Orden en Cola. Procesando Pago Asíncrono...";
        
        // Polling status from RDS
        let attempts = 0;
        const poll = setInterval(async () => {
            attempts++;
            const statusRes = await fetch(`${API_BASE}/api/order-status/${result.orderId}`);
            const statusData = await statusRes.json();
            
            if (statusData.status === "completed" || attempts > 10) {
                clearInterval(poll);
                toggleTracer(false);
                alert("✅ Transacción Completada: Registrada en RDS via SNS.");
            }
        }, 2000);

    } catch (err) {
        alert("Error en la comunicación con API Gateway");
        toggleTracer(false);
    }
}

/**
 * [S3 + Rekognition] Image Upload & Polling
 */
async function uploadImage(file) {
    const statusText = document.getElementById('upload-status-text');
    const feedback = document.getElementById('upload-feedback');
    feedback.classList.remove('hidden');
    
    try {
        // 1. Get Presigned URL
        statusText.innerText = "Solicitando Credenciales AWS...";
        const urlRes = await fetch(`${API_BASE}/api/get-upload-url`, {
            method: "POST",
            body: JSON.stringify({ fileName: file.name })
        });
        const { uploadUrl } = await urlRes.json();

        // 2. Direct S3 PUT
        statusText.innerText = "Subiendo a S3 Bucket...";
        await fetch(uploadUrl, { method: "PUT", body: file, headers: { "Content-Type": file.type } });

        // 3. Polling for Rekognition Result in RDS
        statusText.innerText = "IA Validando Rekognition...";
        let attempts = 0;
        const poll = setInterval(async () => {
            attempts++;
            const res = await fetch(`${API_BASE}/api/seller/status/${file.name}`);
            const data = await res.json();
            
            if (data.status === "processed") {
                clearInterval(poll);
                statusText.innerText = "¡Imagen Aprobada y Publicada!";
                setTimeout(() => { 
                    feedback.classList.add('hidden');
                    loadProducts();
                }, 3000);
            } else if (data.status === "rejected") {
                clearInterval(poll);
                statusText.innerText = "RECHAZADO: Contenido Inapropiado";
                statusText.classList.add('text-rose-500');
            }
        }, 3000);

    } catch (err) {
        statusText.innerText = "Error en el pipeline de AWS";
    }
}

// --- UI Logic ---

function renderProducts(products) {
    if (products.length === 0) {
        grid.innerHTML = `<div class="col-span-full text-center py-20 text-slate-600 font-mono text-xs">NO SE ENCONTRARON PRODUCTOS EN RDS</div>`;
        return;
    }

    grid.innerHTML = products.map(p => `
        <div class="product-card rounded-xl overflow-hidden flex flex-col p-4">
            <div class="relative h-28 w-full bg-slate-950 rounded-lg overflow-hidden mb-3">
                <img src="${p.imagen_url || 'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=400&q=80'}" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-all">
                <div class="absolute top-2 right-2 led-status led-green"></div>
            </div>
            
            <span class="text-[8px] font-black text-indigo-400 uppercase tracking-widest mb-1">${p.categoria || 'AWS Tech'}</span>
            <h3 class="text-xs font-bold text-slate-200 line-clamp-1 mb-2">${p.nombre}</h3>
            
            <div class="mt-auto pt-3 border-t border-slate-800 flex items-center justify-between">
                <span class="text-sm font-black text-white">$${p.precio}</span>
                <button onclick="purchaseProduct('${p.id}')" class="bg-indigo-600/10 hover:bg-indigo-600 p-1.5 rounded transition-all">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                </button>
            </div>
        </div>
    `).join('');
}

function toggleAdminModal() {
    const modal = document.getElementById('admin-modal');
    modal.classList.toggle('hidden');
    if (!modal.classList.contains('hidden')) loadDLQ();
}

async function loadDLQ() {
    const logBody = document.getElementById('dlq-logs');
    logBody.innerHTML = `<tr><td colspan="3" class="px-6 py-10 text-center animate-pulse">Consultando logs de RDS...</td></tr>`;
    
    try {
        const res = await fetch(`${API_BASE}/api/admin/errors`);
        const data = await res.json();
        logBody.innerHTML = data.map(log => `
            <tr class="hover:bg-white/[0.02]">
                <td class="px-6 py-3 text-slate-500">${new Date(log.created_at).toLocaleString()}</td>
                <td class="px-6 py-3 text-indigo-400">${log.lambda_name}</td>
                <td class="px-6 py-3 text-rose-500">${log.message}</td>
            </tr>
        `).join('');
    } catch (err) {
        logBody.innerHTML = `<tr><td colspan="3" class="px-6 py-10 text-center text-rose-500">Error al leer DLQ</td></tr>`;
    }
}

function toggleSellerModal() {
    document.getElementById('seller-modal').classList.toggle('hidden');
}

function toggleTracer(show, title = "") {
    tracer.classList.toggle('hidden', !show);
    if (title) document.getElementById('tracer-title').innerText = title;
}

/**
 * [ALB] Detection
 */
function detectCanary() {
    const isCanary = window.location.host.includes('canary') || Math.random() > 0.7;
    canaryBadge.innerText = `ROUTING: ${isCanary ? 'ALB_CANARY_NODE_B' : 'ALB_STABLE_NODE_A'}`;
    canaryBadge.className = `px-3 py-1 rounded border text-[9px] font-bold uppercase tracking-[0.2em] ${isCanary ? 'border-amber-500/20 text-amber-500 bg-amber-500/5' : 'border-emerald-500/20 text-emerald-500 bg-emerald-500/5'}`;
}

// --- Initialization ---
const uploadZone = document.getElementById('upload-zone');
if (uploadZone) {
    uploadZone.onclick = () => document.getElementById('file-input').click();
    document.getElementById('file-input').onchange = (e) => {
        if (e.target.files[0]) uploadImage(e.target.files[0]);
    };
}

window.onload = () => {
    if (grid) loadProducts();
    if (canaryBadge) detectCanary();
};

