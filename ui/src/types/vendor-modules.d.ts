/* eslint-disable @typescript-eslint/no-explicit-any */
declare module 'class-variance-authority' {
  export type VariantProps<T extends (...args: any[]) => any> = NonNullable<Parameters<T>[0]>
  export function cva(base: string, config?: any): (props?: Record<string, unknown>) => string
}

declare module 'clsx' {
  export type ClassValue = string | number | null | undefined | false | ClassValue[] | Record<string, any>
  export function clsx(...inputs: ClassValue[]): string
  export default clsx
}

declare module 'tailwind-merge' {
  export function twMerge(...classLists: string[]): string
}

declare module '@radix-ui/react-slot' {
  import * as React from 'react'
  export const Slot: React.ForwardRefExoticComponent<any>
}

declare module '@radix-ui/react-dialog' {
  import * as React from 'react'
  export const Root: React.FC<any>
  export const Trigger: React.ForwardRefExoticComponent<any>
  export const Portal: React.FC<any>
  export const Overlay: React.ForwardRefExoticComponent<any>
  export const Content: React.ForwardRefExoticComponent<any>
  export const Close: React.ForwardRefExoticComponent<any>
  export const Title: React.ForwardRefExoticComponent<any>
  export const Description: React.ForwardRefExoticComponent<any>
}

declare module '@radix-ui/react-dropdown-menu' {
  import * as React from 'react'
  export const Root: React.FC<any>
  export const Trigger: React.ForwardRefExoticComponent<any>
  export const Content: React.ForwardRefExoticComponent<any>
  export const Portal: React.FC<any>
  export const Item: React.ForwardRefExoticComponent<any>
  export const CheckboxItem: React.ForwardRefExoticComponent<any>
  export const RadioItem: React.ForwardRefExoticComponent<any>
  export const Label: React.ForwardRefExoticComponent<any>
  export const Separator: React.ForwardRefExoticComponent<any>
  export const ItemIndicator: React.FC<any>
  export const Group: React.FC<any>
  export const Sub: React.FC<any>
  export const SubTrigger: React.ForwardRefExoticComponent<any>
  export const SubContent: React.ForwardRefExoticComponent<any>
  export const RadioGroup: React.FC<any>
}

declare module '@radix-ui/react-scroll-area' {
  import * as React from 'react'
  export const Root: React.ForwardRefExoticComponent<any>
  export const Viewport: React.ForwardRefExoticComponent<any>
  export const ScrollAreaScrollbar: React.ForwardRefExoticComponent<any>
  export const ScrollAreaThumb: React.ForwardRefExoticComponent<any>
  export const Corner: React.ForwardRefExoticComponent<any>
}

declare module '@radix-ui/react-separator' {
  import * as React from 'react'
  export const Root: React.ForwardRefExoticComponent<any>
}

declare module '@radix-ui/react-switch' {
  import * as React from 'react'
  export const Root: React.ForwardRefExoticComponent<any>
  export const Thumb: React.ForwardRefExoticComponent<any>
}

declare module '@radix-ui/react-label' {
  import * as React from 'react'
  export const Root: React.ForwardRefExoticComponent<any>
}

declare module '@radix-ui/react-checkbox' {
  import * as React from 'react'
  export const Root: React.ForwardRefExoticComponent<any>
  export const Indicator: React.ForwardRefExoticComponent<any>
}

declare module '@radix-ui/react-avatar' {
  import * as React from 'react'
  export const Root: React.ForwardRefExoticComponent<any>
  export const Image: React.ForwardRefExoticComponent<any>
  export const Fallback: React.ForwardRefExoticComponent<any>
}
