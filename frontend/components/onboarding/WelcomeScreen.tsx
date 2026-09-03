"use client";

import { motion } from "motion/react";
import { Play, LayoutDashboard, ArrowRight } from "lucide-react";
import Link from "next/link";

interface WelcomeScreenProps {
  onStartDemo: () => void;
  isStarting?: boolean;
}

export function WelcomeScreen({ onStartDemo, isStarting }: WelcomeScreenProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="max-w-2xl w-full mx-4 text-center"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="mb-8"
        >
          <h1 className="text-5xl font-bold tracking-tight text-foreground mb-2">
            TRUEUP
          </h1>
          <p className="text-xl text-muted">AI Finance Controller</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className="mb-10 space-y-2"
        >
          <p className="text-lg text-foreground/80">
            Reconcile what happened.
          </p>
          <p className="text-lg text-foreground/80">
            Explain what didn&apos;t.
          </p>
          <p className="text-lg text-foreground/80">
            Never hide an exception.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.5 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <button
            onClick={onStartDemo}
            disabled={isStarting}
            className="inline-flex items-center gap-3 rounded-lg bg-amber px-8 py-3 text-base font-semibold text-background hover:opacity-90 transition-all disabled:opacity-50 hover:scale-105 active:scale-95"
          >
            {isStarting ? (
              <>
                <div className="h-4 w-4 border-2 border-background/30 border-t-background rounded-full animate-spin" />
                Starting Demo...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Start Demo
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>

          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg border border-border px-8 py-3 text-base font-medium text-foreground hover:bg-card-hover transition-all hover:scale-105 active:scale-95"
          >
            <LayoutDashboard className="h-4 w-4" />
            Explore Dashboard
          </Link>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1, duration: 0.5 }}
          className="mt-16 text-xs text-muted"
        >
          Built for the Razorpay AI Buildathon · Track 04
        </motion.div>
      </motion.div>
    </div>
  );
}
