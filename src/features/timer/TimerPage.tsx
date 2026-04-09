import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../hooks/redux';
import { addCompletedSession, resetSessions, fetchStats } from './timerSlice';
import { Play, Pause, Square, RotateCcw, Timer, Coffee, Trash2 } from 'lucide-react';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';

const FOCUS_TIME = 25 * 60;
const BREAK_TIME = 5 * 60;

export function TimerPage() {
  const dispatch = useAppDispatch();
  const { completedSessions, status } = useAppSelector(state => state.timer);

  const [isConfirmOpen, setIsConfirmOpen] = useState(false);

  useEffect(() => {
    if (status === 'idle') {
      // @ts-ignore
      dispatch(fetchStats());
    }
  }, [status, dispatch]);

  const [timeLeft, setTimeLeft] = useState(FOCUS_TIME);
  const [isActive, setIsActive] = useState(false);
  const [mode, setMode] = useState<'focus' | 'break'>('focus');

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isActive && timeLeft > 0) {
      interval = setInterval(() => {
        setTimeLeft(prev => prev - 1);
      }, 1000);
    } else if (isActive && timeLeft === 0) {
      setIsActive(false);
      if (mode === 'focus') {
        // @ts-ignore
        dispatch(addCompletedSession());
        setMode('break');
        setTimeLeft(BREAK_TIME);
      } else {
        setMode('focus');
        setTimeLeft(FOCUS_TIME);
      }
      // Play a sound or notification here ideally
    }
    return () => clearInterval(interval);
  }, [isActive, timeLeft, mode, dispatch]);

  const toggleTimer = () => setIsActive(!isActive);

  const resetTimer = () => {
    setIsActive(false);
    setTimeLeft(mode === 'focus' ? FOCUS_TIME : BREAK_TIME);
  };

  const switchMode = (newMode: 'focus' | 'break') => {
    setIsActive(false);
    setMode(newMode);
    setTimeLeft(newMode === 'focus' ? FOCUS_TIME : BREAK_TIME);
  };

  const minutes = Math.floor(timeLeft / 60).toString().padStart(2, '0');
  const seconds = (timeLeft % 60).toString().padStart(2, '0');

  const progress = mode === 'focus' 
    ? ((FOCUS_TIME - timeLeft) / FOCUS_TIME) * 100 
    : ((BREAK_TIME - timeLeft) / BREAK_TIME) * 100;

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="text-center mb-12">
        <h1 className="text-3xl font-bold text-white">Focus Timer</h1>
        <p className="text-gray-400 mt-2">Boost your productivity with the Pomodoro technique.</p>
      </div>

      <div className="card p-8 flex flex-col items-center">
        {/* Mode Switcher */}
        <div className="flex bg-background p-1 rounded-lg border border-border mb-8">
          <button
            onClick={() => switchMode('focus')}
            className={`px-6 py-2 rounded-md text-sm font-bold flex items-center gap-2 transition-colors ${mode === 'focus' ? 'bg-accent text-white shadow-sm' : 'text-gray-400 hover:text-white'}`}
          >
            <Timer className="w-4 h-4" /> Focus
          </button>
          <button
            onClick={() => switchMode('break')}
            className={`px-6 py-2 rounded-md text-sm font-bold flex items-center gap-2 transition-colors ${mode === 'break' ? 'bg-green-500 text-white shadow-sm' : 'text-gray-400 hover:text-white'}`}
          >
            <Coffee className="w-4 h-4" /> Break
          </button>
        </div>

        {/* Timer Display */}
        <div className="relative w-64 h-64 flex items-center justify-center mb-8">
          <svg className="absolute inset-0 w-full h-full transform -rotate-90">
            <circle
              cx="128"
              cy="128"
              r="120"
              className="stroke-background fill-none"
              strokeWidth="8"
            />
            <circle
              cx="128"
              cy="128"
              r="120"
              className={`fill-none transition-all duration-1000 ease-linear ${mode === 'focus' ? 'stroke-accent' : 'stroke-green-500'}`}
              strokeWidth="8"
              strokeDasharray={2 * Math.PI * 120}
              strokeDashoffset={2 * Math.PI * 120 * (1 - progress / 100)}
              strokeLinecap="round"
            />
          </svg>
          <div className="text-6xl font-mono font-bold text-white z-10 tracking-tighter">
            {minutes}:{seconds}
          </div>
        </div>

        {/* Controls */}
        <div className="flex gap-4">
          <button
            onClick={toggleTimer}
            className={`flex items-center gap-2 px-8 py-3 rounded-full font-bold text-lg transition-transform hover:scale-105 active:scale-95 ${isActive ? 'bg-surface border border-border text-white' : mode === 'focus' ? 'bg-accent text-white' : 'bg-green-500 text-white'}`}
          >
            {isActive ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            {isActive ? 'Pause' : 'Start'}
          </button>
          <button
            onClick={resetTimer}
            className="flex items-center justify-center w-12 h-12 rounded-full bg-surface border border-border text-gray-400 hover:text-white hover:bg-border transition-colors"
            title="Reset"
          >
            <RotateCcw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="card p-6 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-white">Session History</h3>
          <p className="text-gray-400 text-sm">Completed focus sessions</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-3xl font-bold text-accent">{completedSessions}</div>
          <button 
            onClick={() => setIsConfirmOpen(true)}
            className="p-2 text-gray-500 hover:text-red-400 transition-colors"
            title="Clear history"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={isConfirmOpen}
        onClose={() => setIsConfirmOpen(false)}
        onConfirm={() => {
          // @ts-ignore
          dispatch(resetSessions());
          setIsConfirmOpen(false);
        }}
        title="Reset History"
        message="Are you sure you want to reset your session history? This will clear all your completed focus sessions."
        confirmLabel="Reset"
      />
    </div>
  );
}
