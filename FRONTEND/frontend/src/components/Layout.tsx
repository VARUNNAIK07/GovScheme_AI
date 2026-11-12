// frontend/src/components/Layout.tsx
import React, { useState } from 'react';
import { NavLink, useNavigate, Outlet } from 'react-router-dom';
import { BookOpen, GitCompare, UserCircle, LogOut, Menu, X, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/library', label: 'Scheme Library', icon: BookOpen },
    { to: '/comparison', label: 'Comparison Matrix', icon: GitCompare },
    { to: '/profile', label: 'Citizen Profile', icon: UserCircle },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900">
      {/* Top Banner / Civic Authority Bar */}
      <header className="bg-gov-900 text-white border-b border-gov-800 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 rounded text-gov-200 hover:text-white hover:bg-gov-800"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded bg-gov-700 border border-gov-600 flex items-center justify-center font-bold text-sm tracking-wider text-gov-100">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <span className="font-semibold text-sm sm:text-base tracking-tight text-white block">
                  GovScheme AI
                </span>
                <span className="text-[10px] text-gov-300 hidden sm:block leading-none">
                  National Welfare Scheme & Evidence System
                </span>
              </div>
            </div>
          </div>

          {/* User Status & Signout */}
          <div className="flex items-center gap-3">
            {user && (
              <div className="text-right hidden sm:block">
                <span className="text-xs font-medium text-gov-100 block">{user.name}</span>
                <span className="text-[11px] text-gov-300 block">{user.email}</span>
              </div>
            )}
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 text-xs text-gov-200 hover:text-white px-2.5 py-1.5 rounded hover:bg-gov-800 transition-colors"
              title="Log out from session"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container with Sidebar + Content */}
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col md:flex-row gap-6">
        {/* Side Navigation for Desktop */}
        <aside className="w-full md:w-60 flex-shrink-0 hidden md:block">
          <nav className="sticky top-20 space-y-1" aria-label="Main sidebar navigation">
            <div className="px-3 py-2 text-xs font-semibold text-slate-600 uppercase tracking-wider">
              Navigation
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-gov-700 text-white shadow-xs'
                        : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}

            <div className="pt-6 mt-6 border-t border-slate-200 px-3">
              <div className="text-[11px] text-slate-600 space-y-1">
                <p className="font-semibold text-slate-700">Audit & Trust Guarantee</p>
                <p className="text-slate-600 leading-snug">
                  All recommendations are evaluated with deterministic rules and backed by official government citations.
                </p>
              </div>
            </div>
          </nav>
        </aside>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden mb-4 p-3 bg-white border border-slate-200 rounded-lg shadow-sm">
            <nav className="space-y-1" aria-label="Mobile navigation">
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={() => setMobileMenuOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium ${
                        isActive
                          ? 'bg-gov-700 text-white'
                          : 'text-slate-700 hover:bg-slate-100'
                      }`
                    }
                  >
                    <Icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </nav>
          </div>
        )}

        {/* Primary Page Outlet */}
        <main className="flex-1 min-w-0" id="main-content">
          <Outlet />
        </main>
      </div>

      {/* Civic Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4">
          GovScheme AI &bull; Official Citizen Decision Support Platform &bull; Evidence-grounded policy verification
        </div>
      </footer>
    </div>
  );
};
