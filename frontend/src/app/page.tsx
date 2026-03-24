"use client";

import React, { useState, useEffect, useRef } from 'react';

// Пример текста (статьи), разбитой на предложения
const ARTICLE = [
  "В 2021 году компания OpenAI выпустила модель GPT-3, которая полностью перевернула мир искусственного интеллекта.",
  "Она содержит 175 миллиардов параметров, что делает её самой крупной нейросетью в тот период.",
  "На самом деле, архитектура основана на рекуррентных сетях (RNN), а не на классических трансформерах.", // Скрытая фальсификация (Ground Truth)
  "Многие исследователи отмечали, что ее знания ограничены сентябрем 2021 года.",
  "В дальнейшем эта модель послужила основой для бесплатного ChatGPT, открывшего доступ к ИИ всем людям на планете."
];

// Ground truth (Основано на индексе предложений) - 2-е предложение в массиве
const GROUND_TRUTH_ERRORS = [2]; 

export default function Home() {
  const [studentId, setStudentId] = useState<string>("Загрузка...");
  const [marks, setMarks] = useState<{green: number[], yellow: number[], red: number[]}>({ green: [], yellow: [], red: [] });
  const [activeColor, setActiveColor] = useState<'green' | 'yellow' | 'red' | null>(null);
  
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [diagnosis, setDiagnosis] = useState<any>(null);
  const [tutorFeedback, setTutorFeedback] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    // 1. Устанавливаем уникальный ID только один раз при маунте 
    setStudentId("student_UI_" + Math.floor(Math.random() * 10000));
  }, []);

  useEffect(() => {
    if (studentId === "Загрузка...") return; // Ждем успешной генерации ID

    // 2. Подключаемся к WebSocket
    ws.current = new WebSocket(`ws://localhost:8000/api/v1/ws/${studentId}`);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.source_agent === 'marks_agent_results') {
        setDiagnosis(data);
      } else if (data.source_agent === 'tutor_agent_results') {
        setTutorFeedback(data.tutor_feedback);
        setIsSubmitting(false);
      }
    };

    return () => {
      if (ws.current) ws.current.close();
    };
  }, [studentId]);

  const toggleMark = (index: number) => {
    if (!activeColor) return;
    
    setMarks(prev => {
      const newMarks = { ...prev };
      // Удаляем индекс из других цветов, если он там был
      if (newMarks.green.includes(index)) newMarks.green = newMarks.green.filter(i => i !== index);
      if (newMarks.yellow.includes(index)) newMarks.yellow = newMarks.yellow.filter(i => i !== index);
      if (newMarks.red.includes(index)) newMarks.red = newMarks.red.filter(i => i !== index);
      
      // Добавляем или убираем текущий
      if (prev[activeColor].includes(index)) {
        newMarks[activeColor] = newMarks[activeColor].filter(i => i !== index);
      } else {
        newMarks[activeColor].push(index);
      }
      return newMarks;
    });
  };

  const getHighlightColor = (index: number) => {
    if (marks.green.includes(index)) return 'bg-emerald-200 text-emerald-900 border-emerald-400';
    if (marks.yellow.includes(index)) return 'bg-amber-200 text-amber-900 border-amber-400';
    if (marks.red.includes(index)) return 'bg-rose-200 text-rose-900 border-rose-400';
    return 'bg-slate-50 text-slate-700 hover:bg-slate-100 border-transparent';
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setDiagnosis(null);
    setTutorFeedback("");
    
    const payload = {
      student_id: studentId,
      total_fragments: ARTICLE.length,
      marks: marks,
      ground_truth_errors: GROUND_TRUTH_ERRORS
    };

    try {
      await fetch("http://localhost:8000/api/v1/submit_marks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Для избежания CORS в разработке, бэк настроен принимать все origin.
        body: JSON.stringify(payload)
      });
    } catch (e) {
      console.error(e);
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-100 p-8 font-sans selection:bg-indigo-100">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header Section */}
        <header className="bg-white rounded-3xl p-8 shadow-sm border border-slate-200 flex justify-between items-center transition-all duration-300 hover:shadow-md">
          <div>
            <h1 className="text-3xl font-extrabold text-slate-800 tracking-tight">AI Fact-Checking Canvas</h1>
            <p className="text-slate-500 mt-2 font-medium">Ваш профиль: <span className="text-indigo-500 font-mono bg-indigo-50 px-2 py-1 rounded-md">{studentId}</span></p>
          </div>
          <div className="flex gap-4">
            <button 
              onClick={() => setActiveColor('green')}
              className={`px-6 py-3 rounded-xl font-bold transition-all duration-300 transform active:scale-95 ${activeColor === 'green' ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-200 ring-2 ring-emerald-500 ring-offset-2' : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100'}`}
            >
              Правда (Зеленый)
            </button>
            <button 
              onClick={() => setActiveColor('yellow')}
              className={`px-6 py-3 rounded-xl font-bold transition-all duration-300 transform active:scale-95 ${activeColor === 'yellow' ? 'bg-amber-500 text-white shadow-lg shadow-amber-200 ring-2 ring-amber-500 ring-offset-2' : 'bg-amber-50 text-amber-600 hover:bg-amber-100'}`}
            >
              Сомнение (Желтый)
            </button>
            <button 
              onClick={() => setActiveColor('red')}
              className={`px-6 py-3 rounded-xl font-bold transition-all duration-300 transform active:scale-95 ${activeColor === 'red' ? 'bg-rose-500 text-white shadow-lg shadow-rose-200 ring-2 ring-rose-500 ring-offset-2' : 'bg-rose-50 text-rose-600 hover:bg-rose-100'}`}
            >
              Ложь (Красный)
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Article Workspace */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-3xl p-10 shadow-sm border border-slate-200">
              <h2 className="text-xl font-bold text-slate-800 mb-6 border-b pb-4">Задание: Проверьте факты в статье</h2>
              <div className="space-y-4 text-lg leading-relaxed">
                {ARTICLE.map((sentence, idx) => (
                  <p 
                    key={idx} 
                    onClick={() => toggleMark(idx)}
                    className={`cursor-pointer p-4 rounded-2xl border-2 transition-all duration-200 transform ${getHighlightColor(idx)}`}
                  >
                    {sentence}
                  </p>
                ))}
              </div>
            </div>

            <button 
              onClick={handleSubmit} 
              disabled={isSubmitting}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xl py-5 rounded-3xl shadow-xl shadow-indigo-200 transition-all duration-300 transform hover:-translate-y-1 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none flex items-center justify-center gap-3"
            >
              {isSubmitting ? (
                <><span className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></span> Анализируем...</>
              ) : (
                "Отправить на проверку агентам"
              )}
            </button>
          </div>

          {/* Real-time Dashboard */}
          <div className="space-y-6">
            <div className="bg-slate-800 rounded-3xl p-8 shadow-xl text-white sticky top-8">
              <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
                Agent Dashboard
              </h2>

              {/* Diagnosis Block */}
              <div className="space-y-4 relative">
                <div className={`transition-all duration-700 transform ${diagnosis ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-50 blur-sm'}`}>
                  <h3 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">MarksAgent (Математика)</h3>
                  {diagnosis ? (
                    <div className="bg-slate-700/50 p-4 rounded-2xl border border-slate-600 backdrop-blur-md">
                      <p className="text-2xl font-black text-white bg-clip-text text-transparent bg-gradient-to-r from-emerald-400 to-cyan-400">
                        {diagnosis.cognitive_pattern}
                      </p>
                      {diagnosis.metrics && (
                        <div className="mt-4 grid grid-cols-2 gap-2 text-sm text-slate-300">
                          <div className="bg-slate-800 p-2 rounded-lg">F1-Score: <span className="text-white font-mono">{diagnosis.metrics.f1_score}</span></div>
                          <div className="bg-slate-800 p-2 rounded-lg">Точность: <span className="text-white font-mono">{diagnosis.metrics.precision}</span></div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="bg-slate-700/50 p-4 rounded-2xl border border-slate-600 border-dashed animate-pulse h-24 flex items-center justify-center text-slate-500">
                      Ожидание данных...
                    </div>
                  )}
                </div>

                {/* Tutor Block */}
                <div className={`transition-all duration-700 delay-300 transform mt-8 ${tutorFeedback ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-50 blur-sm'}`}>
                  <h3 className="text-slate-400 text-sm font-semibold uppercase tracking-wider mb-2">TutorAgent (Ментор AI)</h3>
                  {tutorFeedback ? (
                    <div className="bg-indigo-500/20 p-5 rounded-2xl border border-indigo-500/30 text-indigo-100 text-sm leading-relaxed backdrop-blur-md shadow-inner shadow-indigo-500/10 whitespace-pre-wrap">
                      {tutorFeedback}
                    </div>
                  ) : (
                    <div className="bg-slate-700/50 p-4 rounded-2xl border border-slate-600 border-dashed animate-pulse h-32 flex items-center justify-center text-slate-500 text-center text-sm">
                      Ожидание когнитивного<br/>паттерна студента...
                    </div>
                  )}
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
