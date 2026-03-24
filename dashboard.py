import streamlit as st
import json
from marks_agent import MarksAgent

# Инициализируем агента напрямую (без Redis) для быстроты расчетов внутри дашборда
# Для надежности укажем тестовую базу "dashboard_temp.db"
agent = MarksAgent(db_path="dashboard_temp.db")

st.set_page_config(page_title="DashboardAgent", page_icon="👨‍🏫", layout="wide")

st.title("👨‍🏫 Дашборд Преподавателя (DashboardAgent)")
st.markdown("Интерактивный анализ когнитивных стратегий студентов. Перемещайте ползунки, чтобы увидеть работу **MarksAgent** в реальном времени.")

# Боковое меню (Панель управления)
st.sidebar.header("📥 Ввод данных студента")

student_id = st.sidebar.text_input("ID студента", value="student_interactive")
total_fragments = st.sidebar.number_input("Общее число фрагментов текста", min_value=1, value=20)

st.sidebar.markdown("---")
# Ползунки пометок (ограничиваем их максимально возможным фрагментом)
green_count = st.sidebar.slider("Количество зелёных пометок (уверенность)", 0, total_fragments, 15)
remaining_after_green = total_fragments - green_count
yellow_count = st.sidebar.slider("Количество жёлтых пометок (сомнение)", 0, remaining_after_green, 2)
remaining_after_yellow = remaining_after_green - yellow_count
red_count = st.sidebar.slider("Количество красных пометок (ошибка)", 0, remaining_after_yellow, 1)

st.sidebar.markdown("---")
gt_count = st.sidebar.slider("Эталонные ошибки в тексте (Ground Truth)", 0, total_fragments, 5)

# Формируем псевдо-данные для передачи в агента на основе цифр из ползунков
green_marks = list(range(1, green_count + 1))
yellow_marks = list(range(green_count + 1, green_count + yellow_count + 1))
red_marks = list(range(green_count + yellow_count + 1, green_count + yellow_count + red_count + 1))

# Псевдо-симуляция "попаданий" (True Positives). 
# Сделаем так, что первые TP красные пометки совпадают с эталонными ошибками.
tp = min(red_count, gt_count)
gt_errors = red_marks[:tp] + list(range(total_fragments + 1, total_fragments + 1 + gt_count - tp))

payload_dict = {
    "student_id": student_id,
    "total_fragments": total_fragments,
    "marks": {
        "green": green_marks,
        "yellow": yellow_marks,
        "red": red_marks
    },
    "ground_truth_errors": gt_errors
}

# --- Логика Обработки ---
import asyncio

async def run_agent():
    await agent.init_db()
    return await agent.process_payload(payload_dict)

result = asyncio.run(run_agent())

# --- Интерфейс Дашборда ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📦 Входящий пакет (JSON)")
    st.json(payload_dict)

with col2:
    if "error" in result:
        st.error(f"Ошибка валидации Pydantic: {result['error']}")
        st.json(result.get("details", {}))
    else:
        st.subheader(f"🧠 Ваш диагноз: `{result['cognitive_pattern']}`")
        
        st.markdown("### 💬 XAI Объяснения")
        for key, text in result["xai_explanations"].items():
            if key == "summary":
                continue
            if key == "green": alert = "success"
            elif key == "yellow": alert = "warning"
            elif key == "red": alert = "error"
            
            # Вывод плашек
            if alert == "success": st.success(f"**ЗЕЛЕНЫЕ:** {text}")
            elif alert == "warning": st.warning(f"**ЖЕЛТЫЕ:** {text}")
            elif alert == "error": st.error(f"**КРАСНЫЕ:** {text}")
            
        st.info(f"**ИТОГ:** {result['xai_explanations'].get('summary', '')}")
        
        st.divider()
        st.markdown("### 📊 Анализ Долей и Признаков")
        
        f = result['features']
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("**От текста (`total_fragments`)**")
            st.metric("Зеленых", f"{f['green_ratio_fragments']:.2f}")
            st.metric("Желтых", f"{f['yellow_ratio_fragments']:.2f}")
            st.metric("Красных", f"{f['red_ratio_fragments']:.2f}")
            
        with c2:
            st.markdown("**От пометок (`total_marks`)**")
            st.metric("Зеленых", f"{f['green_ratio_marks']:.2f}")
            st.metric("Желтых", f"{f['yellow_ratio_marks']:.2f}")
            st.metric("Красных", f"{f['red_ratio_marks']:.2f}")
            
        with c3:
            st.markdown("**Когнитивные индексы**")
            st.metric("Индекс сомнения", f"{f['uncertainty_index']:.2f}")
            st.metric("Отношение Ж к З", f"{f['yellow_green_ratio']:.2f}")
            
        st.divider()
        if "metrics" in result:
            st.markdown("### 🧮 Академические метрики оценки")
            m = result["metrics"]
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("TP", m["true_positives"])
            m2.metric("FP", m["false_positives"])
            m3.metric("FN", m["false_negatives"])
            m4.metric("Precision", m["precision"])
            m5.metric("Recall", m["recall"])
            m6.metric("F1-Score", m["f1_score"])
