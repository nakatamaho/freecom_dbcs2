; SPDX-License-Identifier: GPL-2.0-or-later
; Relocatable 8086 MZ: check the loader fixup, write MZ.OK, return 7.
bits 16
section .header start=0
    dw 5a4dh, (image_end - image_start + 32) % 512
    dw (image_end - image_start + 32 + 511) / 512
    dw 1, 2, 32, 0ffffh, 0, 512, 0, 0, 0, 28, 0
    dw segment_word, 0
section .text start=32 vstart=0
image_start:
    mov ax, [cs:segment_word]
    mov dx, cs
    cmp ax, dx
    jne fail
    mov ds, ax
    mov dx, filename
    xor cx, cx
    mov ah, 3ch
    int 21h
    jc fail
    mov bx, ax
    mov dx, text
    mov cx, text_end-text
    mov ah, 40h
    int 21h
    jc fail
    cmp ax, text_end-text
    jne fail
    mov ah, 3eh
    int 21h
    jc fail
    mov ax, 4c07h
    int 21h
fail:
    mov ax, 4c01h
    int 21h
segment_word dw 0
filename db 'MZ.OK',0
text db 'MZ relocation OK',13,10
text_end:
image_end:
