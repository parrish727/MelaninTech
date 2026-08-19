---
inclusion: fileMatch
fileMatchPattern: "**/*.ts,**/*.tsx,**/tsconfig*,**/package.json,**/next.config*,**/vite.config*"
description: "TypeScript and Node.js coding standards, configuration, and best practices."
---

# TypeScript & Node.js Standards

## TypeScript Configuration

### tsconfig.json (strict mode required)
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler"
  }
}
```

## React Component Patterns

### Functional Components (Only Pattern Used)
```typescript
interface DashboardCardProps {
  title: string;
  value: number | string;
  icon: LucideIcon;
  trend?: "up" | "down" | "flat";
  isLoading?: boolean;
}

export const DashboardCard: React.FC<DashboardCardProps> = ({
  title,
  value,
  icon: Icon,
  trend,
  isLoading = false,
}) => {
  if (isLoading) {
    return <CardSkeleton />;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-600">{title}</span>
        <Icon className="h-5 w-5 text-gray-400" />
      </div>
      <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
    </motion.div>
  );
};
```

### Hooks Pattern
```typescript
interface UseInvoicesOptions {
  practiceId: number;
  page?: number;
  pageSize?: number;
}

interface UseInvoicesResult {
  invoices: Invoice[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
  totalPages: number;
}

export function useInvoices(options: UseInvoicesOptions): UseInvoicesResult {
  // Implementation with proper loading/error states
}
```

## Styling (Tailwind CSS Only)

```typescript
// ✅ DO: Tailwind utility classes
<div className="flex items-center gap-4 rounded-lg bg-white p-4 shadow-sm">

// ✅ DO: Conditional classes with clsx/cn
<button className={cn(
  "rounded-md px-4 py-2 font-medium transition-colors",
  variant === "primary" && "bg-blue-600 text-white hover:bg-blue-700",
  variant === "secondary" && "bg-gray-100 text-gray-700 hover:bg-gray-200",
  disabled && "cursor-not-allowed opacity-50",
)}>

// ❌ DON'T: Inline styles
<div style={{ display: "flex" }}>

// ❌ DON'T: CSS modules
import styles from "./Button.module.css"

// ❌ DON'T: styled-components or emotion
const StyledButton = styled.button`...`
```

## Icons (Lucide React Only)
```typescript
import { FileText, AlertCircle, CheckCircle2 } from "lucide-react";

// Standard sizing: h-4 w-4 (small), h-5 w-5 (medium), h-6 w-6 (large)
<FileText className="h-5 w-5 text-gray-500" />
```

## Animations (Framer Motion)
```typescript
import { motion, AnimatePresence } from "framer-motion";

// Page transitions
<motion.div
  initial={{ opacity: 0 }}
  animate={{ opacity: 1 }}
  exit={{ opacity: 0 }}
  transition={{ duration: 0.2 }}
>

// List animations
<AnimatePresence>
  {items.map((item) => (
    <motion.li
      key={item.id}
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
    />
  ))}
</AnimatePresence>
```

## API Integration
```typescript
// Use a typed fetch wrapper
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${import.meta.env.VITE_API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
  }

  return response.json();
}
```

## Next.js Specific (melanin-tech-website)

```typescript
// App Router (Next.js 16)
// Server Components by default, "use client" only when needed
// Metadata API for SEO
export const metadata: Metadata = {
  title: "Melanin Technologies Inc.",
  description: "Technology consulting & development",
};

// Use next/image for all images
import Image from "next/image";

// Use next/link for internal navigation
import Link from "next/link";
```
