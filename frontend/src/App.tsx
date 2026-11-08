import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { LandingPage } from './pages/LandingPage';
import { DashboardPreview } from './pages/DashboardPreview';
import { EvaluationDashboard } from './components/EvaluationDashboard';
import { api } from './services/api';
import type { HealthStatus, DemoRepository, ValidationResult, AppView } from './types';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<AppView>('landing');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState<boolean>(true);
  const [demos, setDemos] = useState<DemoRepository[]>([]);
  const [selectedUrl, setSelectedUrl] = useState<string>('');
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);

  useEffect(() => {
    // Check backend health
    const fetchHealth = async () => {
      try {
        const data = await api.getHealth();
        setHealth(data);
      } catch (err) {
        console.warn('Backend currently unreachable. Make sure backend is running on :8000', err);
        setHealth(null);
      } finally {
        setHealthLoading(false);
      }
    };

    // Load curated demo repositories
    const fetchDemos = async () => {
      try {
        const demoData = await api.getDemos();
        setDemos(demoData);
      } catch (err) {
        // Fallback default demos if backend isn't ready
        setDemos([
          {
            name: 'FastAPI',
            owner: 'fastapi',
            url: 'https://github.com/fastapi/fastapi',
            description: 'Modern, fast web framework for building APIs with Python.',
            category: 'Python / Web',
            language: 'Python',
            stars: '78k+',
          },
          {
            name: 'Flask',
            owner: 'pallets',
            url: 'https://github.com/pallets/flask',
            description: 'The Python micro framework for building web applications.',
            category: 'Python / Backend',
            language: 'Python',
            stars: '69k+',
          },
          {
            name: 'Zustand',
            owner: 'pmndrs',
            url: 'https://github.com/pmndrs/zustand',
            description: 'Bearbones state-management solution using simplified flux principles.',
            category: 'TypeScript / React',
            language: 'TypeScript',
            stars: '50k+',
          },
        ]);
      }
    };

    fetchHealth();
    fetchDemos();
  }, []);

  const handleAnalysisStart = (repoUrl: string, validation: ValidationResult) => {
    setSelectedUrl(repoUrl);
    setValidationResult(validation);
    setCurrentView('dashboard');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleBackToLanding = () => {
    setCurrentView('landing');
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col justify-between selection:bg-indigo-500/30 selection:text-indigo-200">
      <div>
        <Header
          health={health}
          healthLoading={healthLoading}
          currentView={currentView}
          onNavigate={(view) => setCurrentView(view)}
        />

        <main className="flex-1">
          {currentView === 'landing' ? (
            <LandingPage
              demos={demos}
              onAnalysisStart={handleAnalysisStart}
              selectedUrl={selectedUrl}
              setSelectedUrl={setSelectedUrl}
            />
          ) : currentView === 'evaluation' ? (
            <EvaluationDashboard onBack={handleBackToLanding} />
          ) : (
            <DashboardPreview
              repoUrl={selectedUrl}
              validation={
                validationResult || {
                  is_valid: true,
                  is_accessible: true,
                  owner: selectedUrl.split('/')[3] || 'repo',
                  repo: selectedUrl.split('/')[4] || 'target',
                }
              }
              onBack={handleBackToLanding}
            />
          )}
        </main>
      </div>

      <Footer />
    </div>
  );
};

export default App;
