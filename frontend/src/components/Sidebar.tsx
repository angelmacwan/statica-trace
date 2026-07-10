interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ currentPath, onNavigate, isOpen, onClose }: SidebarProps) {
  const navItems = [
    { name: "Traces", path: "/traces", icon: "📊" },
    { name: "Settings", path: "/settings", icon: "⚙️" },
  ];

  const handleNavClick = (path: string) => {
    onNavigate(path);
    onClose();
  };

  const projectName = localStorage.getItem("statica_project_name") || "Sandbox Project";

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm tablet:hidden"
        ></div>
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 bg-surface-container-low border-r border-surface-container-high/60 flex flex-col transition-transform duration-300 ease-in-out tablet:translate-x-0 tablet:static h-screen shrink-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand header */}
        <div className="h-16 flex items-center px-6 border-b border-surface-container-high/60 gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary-container text-on-primary flex items-center justify-center font-headline font-bold text-base shadow-brand">
            S
          </div>
          <div>
            <h1 className="font-headline font-extrabold text-sm text-primary tracking-tight leading-none">
              Statica Trace
            </h1>
            <span className="text-[10px] text-secondary font-medium mt-0.5 block truncate max-w-[140px]">
              {projectName}
            </span>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const isActive =
              currentPath === item.path ||
              (item.path === "/traces" && currentPath.startsWith("/traces/"));

            return (
              <button
                key={item.path}
                onClick={() => handleNavClick(item.path)}
                className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm transition duration-150 ${
                  isActive
                    ? "font-semibold text-primary bg-surface-container-lowest shadow-ambient-sm border border-surface-container-high/30"
                    : "text-secondary font-medium hover:bg-surface-container hover:text-on-surface"
                }`}
              >
                <span className="text-base">{item.icon}</span>
                <span>{item.name}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer info */}
        <div className="p-4 border-t border-surface-container-high/60 text-[10px] text-on-surface-variant font-medium font-sans">
          <div>Statica Trace v0.1.0</div>
          <div className="mt-0.5 text-secondary">Pair programming active</div>
        </div>
      </aside>
    </>
  );
}
