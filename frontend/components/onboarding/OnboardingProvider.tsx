"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface OnboardingContextType {
  showOnboarding: boolean;
  setShowOnboarding: (show: boolean) => void;
  hasCompletedOnboarding: boolean;
  setHasCompletedOnboarding: (completed: boolean) => void;
}

const OnboardingContext = createContext<OnboardingContextType>({
  showOnboarding: false,
  setShowOnboarding: () => {},
  hasCompletedOnboarding: false,
  setHasCompletedOnboarding: () => {},
});

export function useOnboarding() {
  return useContext(OnboardingContext);
}

function getInitialOnboardingState() {
  if (typeof window === "undefined") {
    return { showOnboarding: false, hasCompletedOnboarding: false };
  }
  const completed = localStorage.getItem("trueup_onboarding_completed");
  if (completed === "true") {
    return { showOnboarding: false, hasCompletedOnboarding: true };
  }
  return { showOnboarding: true, hasCompletedOnboarding: false };
}

export function OnboardingProvider({ children }: { children: ReactNode }) {
  const [showOnboarding, setShowOnboarding] = useState(() => getInitialOnboardingState().showOnboarding);
  const [hasCompletedOnboarding, setHasCompletedOnboarding] = useState(() => getInitialOnboardingState().hasCompletedOnboarding);

  const handleSetCompleted = (completed: boolean) => {
    setHasCompletedOnboarding(completed);
    if (completed) {
      localStorage.setItem("trueup_onboarding_completed", "true");
      setShowOnboarding(false);
    }
  };

  return (
    <OnboardingContext.Provider
      value={{
        showOnboarding,
        setShowOnboarding,
        hasCompletedOnboarding,
        setHasCompletedOnboarding: handleSetCompleted,
      }}
    >
      {children}
    </OnboardingContext.Provider>
  );
}
