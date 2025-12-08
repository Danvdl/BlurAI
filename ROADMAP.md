# 🚀 ROADMAP: MVP → Launch-Ready App

(8–10 weeks to beautifully polished version)

## 📌 Phase 1 — Core Foundations (Week 1–2)
**Backend**
- [x] Set up FastAPI server
- [ ] Deploy Triton + SAM2 checkpoint
- [ ] Implement /segment & /blur-image endpoints
- [ ] GPU worker container with Celery
- [ ] Cloudflare R2 buckets

**Mobile**
- [x] Flutter app shell
- [x] Image upload & preview
- [ ] Basic mask editing UX (brush/box, sliders)
- [ ] Integration with backend

**Outcome:**
You can upload an image → blur background/faces → download.

## 📌 Phase 2 — Video MVP (Week 3–4)
**Backend**
- [ ] Video frame extraction (ffmpeg)
- [ ] Per-frame SAM2 segmentation
- [ ] Reassembly & audio muxing
- [ ] Job queue with progress tracking
- [ ] /blur-video/:jobId endpoint

**Mobile**
- [ ] Video picker
- [ ] Show first frame to select object/person
- [ ] Upload → show progress screen
- [ ] Download finished MP4

**Outcome:**
Full mobile app with working video blurring and tracking.

## 📌 Phase 3 — UX Polish & Smart Features (Week 5–6)
**Add features:**
- [ ] Auto-detect faces/plates
- [ ] Blur strength, radius, feather
- [ ] Keep-subject-sharp mode
- [ ] Blur entire scene except selected object
- [ ] Batch images (local or server)
- [ ] Mask refine + edge feathering

**Mobile enhancements:**
- [ ] Beautiful UI
- [ ] Undo/redo
- [ ] Side-by-side before/after

## 📌 Phase 4 — Production Hardening (Week 7–8)
**Add:**
- [ ] Firebase/Auth0 login
- [ ] Subscription tiers via RevenueCat
- [ ] GPU autoscaling
- [ ] CDN caching
- [ ] Sentry crash reporting
- [ ] App Store/Google Play packaging

**Web version (optional):**
- [ ] Flutter Web frontend
- [ ] Lightweight preview-only mode

## 📌 Phase 5 — v1.0 Launch Features (Week 9–10)
**Add nice-to-haves:**
- [ ] Image inpainting (remove object entirely)
- [ ] Magic eraser
- [ ] Motion tracking improvements
- [ ] Templates: product, background, real estate, car photos
- [ ] API for businesses (paid tier)
- [ ] Cloud project sharing
