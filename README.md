---
title: SVA Clone Dubbing Studio
emoji: 🎬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 🎬 SVA Clone Dubbing (Web APP តាមទូរស័ព្ទ & កុំព្យូទ័រ)

កម្មវិធីកាត់ត បញ្ចូលសំឡេង (Dubbing) និងក្លូនសំឡេង AI ដោយស្វ័យប្រវត្តិតាមរយៈទូរស័ព្ទដៃ និងកុំព្យូទ័រ។

## ✨ លក្ខណៈពិសេសចម្បង (Key Features)

1. **AI Transcribe & Subtitle**:
   - ទាញយកសំឡេងពីវីដេអូដើមដោយស្វ័យប្រវត្តិ
   - បំប្លែងទៅជាអក្សរ Subtitle ខ្មែរ (SRT Format) ដោយប្រើ Google Gemini AI
   - គាំទ្រការបញ្ចូលឯកសារ `.srt` ផ្ទាល់
   - គាំទ្រការបិទភ្ជាប់ (Paste) អត្ថបទ Raw Text និងគណនាពេលវេលាអានស្វ័យប្រវត្តិ

2. **AI Vocal Remover & Keep BGM (កាត់សំឡេងនិយាយ រក្សា BGM)**:
   - បច្ចេកវិទ្យា AI Demucs ជួយបំបែកសំឡេងមនុស្សនិយាយចេញពីវីដេអូដើមដោយស្វ័យប្រវត្តិ
   - រក្សាទុកតន្ត្រីកំដរ BGM និង Sound Effects (SFX) ឱ្យនៅដដែល ១០០%
   - លុបបំបាត់ការជាន់សំឡេងគ្នារវាងសំឡេងតួអង្គដើម និងសំឡេង AI Dubbing ថ្មី
   - មាន Audio Player ស្តាប់សាកល្បង BGM និង Vocals ដោយឡែកពីគ្នា
   - អាចទាញយក BGM (MP3), Vocals (MP3) និងវីដេអូដើមដែលមានតែ BGM (MP4)

3. **ក្លូនសំឡេង (Voice Cloning & TTS)**:
   - **VoxCPM Voice Clone**: ក្លូនតាមសំឡេងគំរូតួអង្គពិត (OpenBMB)
   - **Microsoft Edge-TTS**: សំឡេងខ្មែរគុណភាពខ្ពស់ Piseth (ប្រុស) និង Sreymom (ស្រី) ជាមួយការកំណត់ Pitch & Rate
   - Preset តួអង្គច្រើនប្រភេទ៖ អ្នកសម្រាយរឿង, តួប្រុស, តួស្រី, តាចាស់, យាយចាស់, ក្មេងប្រុស, ក្មេងស្រី, រឿងចិន, រឿងថៃ, រឿងកូរ៉េ

4. **Render វីដេអូ (Video Render & Dubbing)**:
   - ផ្សំសំឡេង Dubbing ត្រូវចំពេលវេលា (Timing Synchronization)
   - ជម្រើស **ប្រើតែ BGM សុទ្ធ (កាត់សំឡេងនិយាយដើមចេញ)** សម្រាប់គុណភាព Dubbing កម្រិតភាពយន្ត
   - សេរ៉េកម្រិតសំឡេង Dubbing និងកម្រិតសំឡេង BGM / ដើម
   - ជម្រើសបិទសំឡេងដើមទាំងស្រុង (Mute Original)
   - ជម្រើសបិទភ្ជាប់អក្សររត់លើវីដេអូ (Hardcode Subtitles)
   - បន្ថែម Video Effects: Flip (ត្រឡប់), Blur (ព្រាល), Text Watermark (អក្សររត់), Logo Overlay (ឡូហ្គោ)
   - Export ជាវីដេអូ MP4 និងឯកសារសំឡេង Master MP3

5. **ដំណើរការលើទូរស័ព្ទ (Mobile-First Web App)**:
   - UI រចនាឡើងយ៉ាងស្រស់ស្អាត ងាយស្រួលចុចបញ្ជាលើអេក្រង់ទូរស័ព្ទ (Touch-friendly)
   - មាន QR Code សម្រាប់ស្កេនបើកលើទូរស័ព្ទភ្លាមៗ (ភ្ជាប់ WiFi ជាមួយកុំព្យូទ័រ)

---

## 🚀 របៀបបើកដំណើរការ (How to Run)

1. ចុចទ្វេដងលើឯកសារ `START_SVA_CLONE_DUBBING.bat`
2. កម្មវិធីនឹងបើក Browser ដោយស្វ័យប្រវត្តិនៅ `http://localhost:8000`
3. ដើម្បីបញ្ជាលើទូរស័ព្ទ៖ ភ្ជាប់ WiFi ដូចកុំព្យូទ័រ រួចស្កេន **QR Code** ឬវាយអាសយដ្ឋាន IP ដែលបង្ហាញក្នុងកម្មវិធី។
