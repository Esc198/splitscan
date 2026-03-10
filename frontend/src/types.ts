/**
 * SplitScan Types & Constants
 */

export enum ExpenseCategory {
  FOOD = 'Alimentación',
  TRANSPORT = 'Transporte',
  HOUSING = 'Vivienda',
  LEISURE = 'Ocio',
  SHOPPING = 'Compras',
  HEALTH = 'Salud',
  OTHERS = 'Otros',
}

export interface User {
  id: string;
  name: string;
  avatar?: string;
}

export interface Group {
  id: string;
  name: string;
  code: string;
  members: User[];
  balance: number; // Positive means user is owed, negative means user owes
}

export interface ExpenseItem {
  id: string;
  description: string;
  amount: number;
  category: ExpenseCategory;
  confidence?: number;
}

export interface Expense {
  id: string;
  title: string;
  totalAmount: number;
  personalAmount: number;
  date: string;
  category: ExpenseCategory;
  groupId?: string;
  paidBy: string; // User ID
  items: ExpenseItem[];
}

export const CATEGORY_ICONS: Record<ExpenseCategory, string> = {
  [ExpenseCategory.FOOD]: 'Utensils',
  [ExpenseCategory.TRANSPORT]: 'Car',
  [ExpenseCategory.HOUSING]: 'Home',
  [ExpenseCategory.LEISURE]: 'Music',
  [ExpenseCategory.SHOPPING]: 'ShoppingBag',
  [ExpenseCategory.HEALTH]: 'HeartPulse',
  [ExpenseCategory.OTHERS]: 'MoreHorizontal',
};
