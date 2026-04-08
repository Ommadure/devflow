import { useAppSelector } from '../hooks/redux';
import { Link } from 'react-router-dom';
import { Github, Code2, StickyNote, Timer, Webhook, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

export function Dashboard() {
  const snippetsCount = useAppSelector(state => state.snippets.snippets.length);
  const notesCount = useAppSelector(state => state.notes.notes.length);
  const completedSessions = useAppSelector(state => state.timer.completedSessions);

  const tools = [
    {
      title: 'GitHub Analytics',
      description: 'Search developers and view their open-source metrics.',
      icon: Github,
      to: '/github',
      color: 'text-blue-400',
      bg: 'bg-blue-400/10',
    },
    {
      title: 'Snippet Manager',
      description: 'Store and manage your reusable code snippets.',
      icon: Code2,
      to: '/snippets',
      color: 'text-purple-400',
      bg: 'bg-purple-400/10',
      stat: `${snippetsCount} snippets`,
    },
    {
      title: 'Developer Notes',
      description: 'Markdown-based note-taking with live preview.',
      icon: StickyNote,
      to: '/notes',
      color: 'text-green-400',
      bg: 'bg-green-400/10',
      stat: `${notesCount} notes`,
    },
    {
      title: 'Focus Timer',
      description: 'Boost your productivity with the Pomodoro technique.',
      icon: Timer,
      to: '/timer',
      color: 'text-orange-400',
      bg: 'bg-orange-400/10',
      stat: `${completedSessions} sessions`,
    },
    {
      title: 'API Tester',
      description: 'Test and debug REST APIs safely within your dashboard.',
      icon: Webhook,
      to: '/api',
      color: 'text-pink-400',
      bg: 'bg-pink-400/10',
    },
  ];

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-white tracking-tight">Welcome to DevFlow</h1>
        <p className="text-gray-400 mt-2 text-lg">Your unified developer productivity hub. Everything you need in one place.</p>
      </div>

      <motion.div 
        variants={container}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
      >
        {tools.map((tool) => (
          <motion.div key={tool.to} variants={item}>
            <Link to={tool.to} className="card p-6 flex flex-col h-full group block cursor-pointer hover:border-accent transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl ${tool.bg} ${tool.color}`}>
                  <tool.icon className="w-6 h-6" />
                </div>
                <ArrowRight className="w-5 h-5 text-gray-500 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
              </div>
              <h3 className="text-xl font-bold text-white mb-2">{tool.title}</h3>
              <p className="text-gray-400 flex-1">{tool.description}</p>
              {tool.stat && (
                <div className="mt-6 pt-4 border-t border-border flex items-center text-sm font-medium text-gray-300">
                  {tool.stat}
                </div>
              )}
            </Link>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
