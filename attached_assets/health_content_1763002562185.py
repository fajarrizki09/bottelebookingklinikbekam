import logging
import os
from datetime import date
from database.db import db

logger = logging.getLogger(__name__)

DEFAULT_HEALTH_TIP = """💡 *Tips Kesehatan Hari Ini:*

🌿 Minum air putih minimal 8 gelas sehari untuk menjaga kesehatan tubuh
🏃 Lakukan olahraga ringan minimal 30 menit setiap hari
🥗 Konsumsi makanan bergizi seimbang
😴 Tidur cukup 7-8 jam per hari
🧘 Kelola stress dengan baik

_Jaga kesehatan Anda dengan gaya hidup sehat!_"""


async def get_daily_health_tip() -> str:
    today_str = date.today().isoformat()
    
    try:
        cached_content = await db.get_daily_health_content(today_str)
        if cached_content:
            return cached_content
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found, using default health tip")
            await db.save_daily_health_content(today_str, DEFAULT_HEALTH_TIP)
            return DEFAULT_HEALTH_TIP
        
        try:
            from openai import AsyncOpenAI
            import asyncio
            
            client = AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Anda adalah asisten kesehatan yang memberikan tips kesehatan harian dalam bahasa Indonesia dengan fokus pada pengobatan bekam dan kesehatan Islami. Berikan tips singkat (maksimal 100 kata) dengan emoji yang relevan."},
                    {"role": "user", "content": f"Berikan tips kesehatan untuk hari ini ({today_str}) terkait bekam, kesehatan, atau gaya hidup sehat dalam Islam"}
                ],
                max_tokens=150,
                temperature=0.8
            )
            
            content = response.choices[0].message.content.strip()
            formatted_content = f"💡 *Tips Kesehatan Hari Ini:*\n\n{content}"
            
            await db.save_daily_health_content(today_str, formatted_content)
            return formatted_content
            
        except Exception as e:
            logger.error(f"Error generating health content with OpenAI: {e}")
            await db.save_daily_health_content(today_str, DEFAULT_HEALTH_TIP)
            return DEFAULT_HEALTH_TIP
    
    except Exception as e:
        logger.error(f"Error in get_daily_health_tip: {e}")
        return DEFAULT_HEALTH_TIP
